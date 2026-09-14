"""Print the GitHub OIDC claims that AWS IAM evaluates for this job."""
import base64
import json
import os
import sys
import urllib.request


def decode_payload(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def main():
    required = ("ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        print(
            "GitHub OIDC request environment is not available. "
            "Run this script inside a GitHub Actions job with 'id-token: write'.",
            file=sys.stderr,
        )
        return 1

    request_url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    separator = "&" if "?" in request_url else "?"
    request_url = f"{request_url}{separator}audience=sts.amazonaws.com"
    request = urllib.request.Request(
        request_url,
        headers={"Authorization": f"bearer {os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        token = json.loads(response.read())["value"]

    claims = decode_payload(token)
    keys = (
        "iss",
        "aud",
        "sub",
        "repository",
        "repository_owner",
        "ref",
        "environment",
        "workflow",
        "job_workflow_ref",
        "actor",
    )
    print(json.dumps({key: claims.get(key) for key in keys}, indent=2, sort_keys=True))

    expected_environment = os.getenv("EXPECTED_ENVIRONMENT")
    if expected_environment:
        expected_sub = f"repo:{os.environ['GITHUB_REPOSITORY']}:environment:{expected_environment}"
        if claims.get("sub") != expected_sub:
            print(
                f"Expected OIDC sub '{expected_sub}' but GitHub issued '{claims.get('sub')}'. "
                "Update the IAM role trust policy or the GitHub Environment name.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
