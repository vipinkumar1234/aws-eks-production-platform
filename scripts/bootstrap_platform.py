"""Bootstrap the Kubernetes platform layer for a rendered environment.

This script is intentionally idempotent. Run it from a host or runner that can
reach the private EKS API endpoint, such as CloudShell VPC, a bastion host, or a
self-hosted GitHub Actions runner in the cluster VPC.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ARGO_VERSION = "10.8.2"


def run(*args):
    subprocess.run(args, check=True)


def output(*args):
    return subprocess.check_output(args, text=True)


def load_outputs(environment):
    return json.loads(output(
        "terraform",
        f"-chdir={ROOT / 'terraform/environments' / environment}",
        "output",
        "-json",
    ))


def require_rendered_tree(environment):
    base = ROOT / "gitops/environments" / environment
    required = [
        base / "argocd/values.yaml",
        base / "argocd/projects/platform-project.yaml",
        base / "argocd/bootstrap/namespace.yaml",
        base / "apps/sample-app/deployment.yaml",
        base / "apps/sample-app/targetgroupbinding.yaml",
        base / "platform/aws-load-balancer-controller/values.yaml",
        base / "platform/karpenter/values.yaml",
        base / "platform/karpenter-resources/nodepool.yaml",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Render GitOps before bootstrap. Missing files: " + ", ".join(missing))
    unresolved = []
    for path in required:
        content = path.read_text(encoding="utf-8")
        if "REPLACE_WITH_" in content or "IMAGE_TAG" in content:
            unresolved.append(str(path.relative_to(ROOT)))
    if unresolved:
        raise SystemExit("Rendered GitOps still has placeholders: " + ", ".join(unresolved))
    deployment = (base / "apps/sample-app/deployment.yaml").read_text(encoding="utf-8")
    if "@sha256:" not in deployment:
        raise SystemExit("sample-app deployment must use an immutable ECR digest before bootstrap")
    return base


def kubectl(context, *args):
    run("kubectl", "--context", context, *args)


def wait_application(context, name, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = subprocess.run([
            "kubectl", "--context", context, "-n", "argocd", "get",
            "application", name, "-o", "json",
        ], text=True, capture_output=True)
        if status.returncode == 0:
            app = json.loads(status.stdout)
            sync = app.get("status", {}).get("sync", {}).get("status")
            health = app.get("status", {}).get("health", {}).get("status")
            if sync == "Synced" and health in ("Healthy", "Progressing"):
                print(f"Argo CD application {name} is {sync}/{health}.")
                return
            print(f"Waiting for Argo CD application {name}: sync={sync}, health={health}")
        else:
            print(f"Waiting for Argo CD application {name} to exist")
        time.sleep(15)
    raise SystemExit(f"Timed out waiting for Argo CD application {name}")


def wait_target_health(region, target_group_arn, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = json.loads(output(
            "aws", "elbv2", "describe-target-health",
            "--region", region,
            "--target-group-arn", target_group_arn,
            "--output", "json",
        ))
        targets = response.get("TargetHealthDescriptions", [])
        states = [target.get("TargetHealth", {}).get("State") for target in targets]
        print(f"Target health states: {states or ['none']}")
        if targets and all(state == "healthy" for state in states):
            return
        time.sleep(20)
    raise SystemExit("Timed out waiting for healthy target group targets")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "prod"], required=True)
    parser.add_argument("--skip-target-health", action="store_true")
    args = parser.parse_args()

    rendered = require_rendered_tree(args.environment)
    outputs = load_outputs(args.environment)
    cluster = outputs["cluster_name"]["value"]
    region = outputs["aws_region"]["value"]
    target_group_arn = outputs["app_target_group_arn"]["value"]
    app_url = outputs["app_url"]["value"]
    context = f"{cluster}-platform-bootstrap"

    run("aws", "eks", "update-kubeconfig", "--region", region, "--name", cluster, "--alias", context)
    kubectl(context, "get", "nodes")

    run(sys.executable, str(ROOT / "scripts/bootstrap_karpenter.py"), "--environment", args.environment)

    run("helm", "repo", "add", "argo", "https://argoproj.github.io/argo-helm")
    run("helm", "repo", "update")
    run(
        "helm", "upgrade", "--install", "argocd", "argo/argo-cd",
        "--version", ARGO_VERSION,
        "--namespace", "argocd",
        "--create-namespace",
        "--kube-context", context,
        "--values", str(rendered / "argocd/values.yaml"),
        "--wait",
        "--timeout", "10m",
    )

    kubectl(context, "apply", "-f", str(rendered / "argocd/projects/platform-project.yaml"))
    kubectl(context, "apply", "-f", str(rendered / "argocd/bootstrap/namespace.yaml"))

    for app in ("platform-root", "observability-root", "sample-app"):
        wait_application(context, app, 600)
    for app in ("aws-load-balancer-controller", "metrics-server", "karpenter-resources", "fluent-bit"):
        wait_application(context, app, 900)

    kubectl(context, "-n", "platform-system", "rollout", "status", "deployment/aws-load-balancer-controller", "--timeout=10m")
    kubectl(context, "wait", "--for=condition=Established", "crd/targetgroupbindings.elbv2.k8s.aws", "--timeout=5m")
    kubectl(context, "wait", "--for=condition=Ready", "ec2nodeclass", "--all", "--timeout=5m")
    kubectl(context, "wait", "--for=condition=Ready", "nodepool", "--all", "--timeout=5m")
    kubectl(context, "-n", "sample-app", "rollout", "status", "deployment/sample-app", "--timeout=10m")
    kubectl(context, "-n", "sample-app", "get", "pods,svc,targetgroupbinding")

    if not args.skip_target_health:
        wait_target_health(region, target_group_arn, 900)

    print(f"Platform bootstrap completed. Open {app_url}")


if __name__ == "__main__":
    main()
