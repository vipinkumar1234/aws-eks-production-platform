#!/usr/bin/env bash
set -euo pipefail
terraform fmt -check -recursive .
command -v tfsec >/dev/null || { echo 'tfsec is required'; exit 1; }
tfsec . --minimum-severity HIGH
