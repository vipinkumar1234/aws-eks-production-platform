#!/usr/bin/env bash
set -euo pipefail
for directory in modules/vpc modules/eks modules/ecr modules/karpenter environments/dev environments/prod; do
  (cd "$directory" && bash check.sh)
done
