"""Validate the pod-to-ALB binding against the pinned controller CRD schema."""
from pathlib import Path
from urllib.request import urlopen
import yaml
from jsonschema import Draft7Validator
from render_gitops import TOKENS, render


def main():
    values = {key: {"value": "example"} for key in TOKENS.values()}
    values.update({"app_target_group_arn": {"value": "arn:aws:elasticloadbalancing:ap-southeast-1:123456789012:targetgroup/game/1234567890123456"},
                   "vpc_id": {"value": "vpc-0123456789abcdef0"},
                   "ecr_repository_url": {"value": "example"}})
    files = render("dev", values, "https://github.com/test/platform.git", "example@sha256:" + "a" * 64)
    binding = yaml.safe_load(files[Path("apps/sample-app/targetgroupbinding.yaml")])
    url = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.13.0/config/crd/bases/elbv2.k8s.aws_targetgroupbindings.yaml"
    with urlopen(url, timeout=30) as response:
        crd = yaml.safe_load(response.read())
    schema = next(v["schema"]["openAPIV3Schema"] for v in crd["spec"]["versions"] if v["name"] == "v1beta1")
    Draft7Validator(schema).validate(binding)
    print("Validated TargetGroupBinding against AWS Load Balancer Controller 2.13.0 CRD")


if __name__ == "__main__":
    main()
