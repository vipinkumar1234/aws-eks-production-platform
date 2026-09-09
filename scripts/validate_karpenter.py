"""Validate rendered Karpenter specs against the pinned release's CRD schemas.

Downloads official schemas; OpenAPI validation does not execute Kubernetes CEL rules.
Server-side dry-run against the installed CRDs remains a deployment gate.
"""
import json
from pathlib import Path
from urllib.request import urlopen
import yaml
from jsonschema import Draft7Validator
from bootstrap_karpenter import VERSION
from render_gitops import TOKENS, render


def main():
    values = {key: {"value": "example"} for key in TOKENS.values()}
    values.update({"resource_prefix": {"value": "game-apse1-dev"},
                   "karpenter_cpu_limit": {"value": 32},
                   "karpenter_ami_id": {"value": "ami-0123456789abcdef0"},
                   "node_security_group_id": {"value": "sg-0123456789abcdef0"},
                   "ecr_repository_url": {"value": "example"}})
    files = render("dev", values, "https://github.com/test/platform.git", "example@sha256:" + "a" * 64)
    documents = list(yaml.safe_load_all(files[Path("platform/karpenter-resources/nodepool.yaml")]))
    schemas = {}
    for document in documents:
        group, version = document["apiVersion"].split("/")
        plural = {"NodePool": "nodepools", "EC2NodeClass": "ec2nodeclasses"}[document["kind"]]
        url = f"https://raw.githubusercontent.com/aws/karpenter-provider-aws/v{VERSION}/pkg/apis/crds/{group}_{plural}.yaml"
        with urlopen(url, timeout=30) as response:
            crd = yaml.safe_load(response.read())
        schema = next(v["schema"]["openAPIV3Schema"] for v in crd["spec"]["versions"] if v["name"] == version)
        Draft7Validator(schema).validate(document)
        schemas[document["kind"]] = schema
        print(f"Validated {document['kind']} against Karpenter {VERSION} CRD")
    # Catch a malformed capacity limit rather than silently validating no schema.
    invalid = json.loads(json.dumps(documents[1]))
    invalid["spec"]["template"]["spec"]["requirements"][0]["operator"] = "INVALID"
    assert list(Draft7Validator(schemas["NodePool"]).iter_errors(invalid)), "Schema validation is not enforcing enums"


if __name__ == "__main__":
    main()
