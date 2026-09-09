"""Scheduling and bootstrap contracts that prevent stranded workloads."""
import unittest
from pathlib import Path
from unittest.mock import patch
import json
import yaml
import bootstrap_karpenter
from render_gitops import TOKENS, render

ROOT = Path(__file__).resolve().parents[1]


class KarpenterTest(unittest.TestCase):
    def rendered(self):
        values = {key: {"value": "example"} for key in TOKENS.values()}
        values.update({"resource_prefix": {"value": "game-apse1-dev"},
                       "karpenter_cpu_limit": {"value": 32},
                       "ecr_repository_url": {"value": "example"}})
        return render("dev", values, "https://github.com/test/platform.git", "example@sha256:" + "a" * 64)

    def test_workloads_match_pool_and_preserve_zone_availability(self):
        files = self.rendered()
        nodeclass, pool = list(yaml.safe_load_all(files[Path("platform/karpenter-resources/nodepool.yaml")]))
        app = list(yaml.safe_load_all(files[Path("apps/sample-app/deployment.yaml")]))[0]
        spec = app["spec"]["template"]["spec"]
        self.assertEqual(spec["nodeSelector"], pool["spec"]["template"]["metadata"]["labels"])
        self.assertEqual(pool["spec"]["template"]["spec"]["nodeClassRef"]["name"], nodeclass["metadata"]["name"])
        self.assertEqual(spec["topologySpreadConstraints"][0]["minDomains"], 2)
        self.assertEqual(pool["spec"]["disruption"]["consolidationPolicy"], "WhenEmptyOrUnderutilized")
        self.assertEqual(pool["spec"]["disruption"]["budgets"], [{"nodes": "1"}])
        self.assertEqual(pool["spec"]["limits"]["cpu"], "32")
        self.assertIn("instanceProfile", nodeclass["spec"])
        self.assertNotIn("role", nodeclass["spec"])
        self.assertFalse(nodeclass["spec"]["associatePublicIPAddress"])
        controller = yaml.safe_load(files[Path("platform/karpenter/values.yaml")])
        self.assertEqual(controller["nodeSelector"]["workload-tier"], "system")
        self.assertNotEqual(controller["nodeSelector"]["workload-tier"], spec["nodeSelector"]["workload-tier"])

    def test_crds_precede_controller_and_context_is_explicit(self):
        outputs = {"cluster_name": {"value": "test-eks"}, "aws_region": {"value": "ap-southeast-1"}}
        with patch("sys.argv", ["bootstrap_karpenter", "--environment", "dev"]), \
             patch.object(bootstrap_karpenter.subprocess, "check_output", return_value=json.dumps(outputs)), \
             patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "read_text", return_value="settings: {}"), \
             patch.object(bootstrap_karpenter, "run") as run:
            bootstrap_karpenter.main()
        calls = [call.args for call in run.call_args_list]
        crd = next(i for i, c in enumerate(calls) if "karpenter-crd" in c)
        controller = next(i for i, c in enumerate(calls) if c[0] == "helm" and "karpenter" in c)
        self.assertLess(crd, controller)
        self.assertIn("--skip-crds", calls[controller])
        for call in calls:
            if call[0] in ("helm", "kubectl"):
                self.assertIn("test-eks-bootstrap", call)


if __name__ == "__main__":
    unittest.main()
