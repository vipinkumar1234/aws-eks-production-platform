import unittest
from pathlib import Path
from unittest.mock import call, patch

import bootstrap_platform


class PlatformBootstrapTest(unittest.TestCase):
    def test_bootstrap_waits_for_platform_and_targets(self):
        outputs = {
            "cluster_name": {"value": "test-eks"},
            "aws_region": {"value": "ap-southeast-1"},
            "app_target_group_arn": {"value": "arn:target"},
            "app_url": {"value": "https://example.cloudfront.net"},
        }
        with patch("sys.argv", ["bootstrap_platform", "--environment", "dev"]), \
             patch.object(bootstrap_platform, "require_rendered_tree", return_value=Path("gitops/environments/dev")), \
             patch.object(bootstrap_platform, "load_outputs", return_value=outputs), \
             patch.object(bootstrap_platform, "run") as run, \
             patch.object(bootstrap_platform, "kubectl") as kubectl, \
             patch.object(bootstrap_platform, "wait_application") as wait_application, \
             patch.object(bootstrap_platform, "wait_target_health") as wait_target_health:
            bootstrap_platform.main()

        run.assert_any_call("aws", "eks", "update-kubeconfig", "--region", "ap-southeast-1", "--name", "test-eks", "--alias", "test-eks-platform-bootstrap")
        self.assertTrue(any("bootstrap_karpenter.py" in str(arg) for args in run.call_args_list for arg in args.args))
        run.assert_any_call(
            "helm", "upgrade", "--install", "argocd", "argo/argo-cd",
            "--version", bootstrap_platform.ARGO_VERSION,
            "--namespace", "argocd",
            "--create-namespace",
            "--kube-context", "test-eks-platform-bootstrap",
            "--values", str(Path("gitops/environments/dev/argocd/values.yaml")),
            "--wait",
            "--timeout", "10m",
        )
        kubectl.assert_any_call("test-eks-platform-bootstrap", "-n", "sample-app", "rollout", "status", "deployment/sample-app", "--timeout=10m")
        wait_application.assert_has_calls([
            call("test-eks-platform-bootstrap", "platform-root", 600),
            call("test-eks-platform-bootstrap", "observability-root", 600),
            call("test-eks-platform-bootstrap", "sample-app", 600),
            call("test-eks-platform-bootstrap", "aws-load-balancer-controller", 900),
            call("test-eks-platform-bootstrap", "metrics-server", 900),
            call("test-eks-platform-bootstrap", "karpenter-resources", 900),
            call("test-eks-platform-bootstrap", "fluent-bit", 900),
        ])
        wait_target_health.assert_called_once_with("ap-southeast-1", "arn:target", 900)


if __name__ == "__main__":
    unittest.main()
