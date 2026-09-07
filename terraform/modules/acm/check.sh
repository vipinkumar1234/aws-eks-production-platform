#!/usr/bin/env bash
set -euo pipefail
terraform fmt -check -recursive .
terraform init -backend=false >/dev/null
terraform validate
