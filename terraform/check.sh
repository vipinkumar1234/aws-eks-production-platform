#!/usr/bin/env bash
set -euo pipefail
terraform fmt -check -recursive .
for environment in dev prod; do
  terraform -chdir="environments/$environment" init -backend=false -input=false
  terraform -chdir="environments/$environment" validate
done
command -v tfsec >/dev/null || { echo 'tfsec is required'; exit 1; }
tfsec . --minimum-severity HIGH
