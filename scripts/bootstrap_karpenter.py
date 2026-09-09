"""Install pinned Karpenter CRDs/controller on the selected environment's cluster."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.12.0"


def run(*args):
    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "prod"], required=True)
    args = parser.parse_args()
    outputs = json.loads(subprocess.check_output([
        "terraform", f"-chdir={ROOT / 'terraform/environments' / args.environment}", "output", "-json"
    ], text=True))
    cluster = outputs["cluster_name"]["value"]
    region = outputs["aws_region"]["value"]
    values = ROOT / "gitops/environments" / args.environment / "platform/karpenter/values.yaml"
    if not values.is_file():
        parser.error("Render and review this environment's GitOps tree first")
    if "REPLACE_WITH_" in values.read_text():
        parser.error("Karpenter values contain unresolved placeholders")
    # Explicit context avoids installing into another currently selected cluster.
    context = f"{cluster}-bootstrap"
    run("aws", "eks", "update-kubeconfig", "--region", region, "--name", cluster, "--alias", context)
    run("kubectl", "--context", context, "get", "nodes")
    run("helm", "upgrade", "--install", "karpenter-crd", "oci://public.ecr.aws/karpenter/karpenter-crd",
        "--version", VERSION, "--namespace", "kube-system", "--kube-context", context,
        "--wait", "--timeout", "5m")
    run("kubectl", "--context", context, "wait", "--for=condition=Established",
        "crd/nodepools.karpenter.sh", "crd/nodeclaims.karpenter.sh",
        "crd/ec2nodeclasses.karpenter.k8s.aws", "--timeout=120s")
    run("helm", "upgrade", "--install", "karpenter", "oci://public.ecr.aws/karpenter/karpenter",
        "--version", VERSION, "--namespace", "kube-system", "--kube-context", context,
        "--skip-crds", "--values", str(values), "--wait", "--timeout", "10m")
    run("kubectl", "--context", context, "-n", "kube-system", "rollout", "status",
        "deployment/karpenter", "--timeout=300s")
    print("Karpenter is ready. Bootstrap Argo CD to reconcile the NodeClass and NodePool.")


if __name__ == "__main__":
    main()
