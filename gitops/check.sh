#!/usr/bin/env bash
set -euo pipefail
bash argocd/check.sh
bash platform/check.sh
bash observability/check.sh
bash apps/sample-app/check.sh
