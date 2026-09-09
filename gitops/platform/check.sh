#!/usr/bin/env bash
set -euo pipefail
command -v kubeconform >/dev/null || { echo 'kubeconform is required'; exit 1; }
find . -name '*.yaml' ! -name values.yaml -print0 | xargs -0 kubeconform -strict -summary -skip Application,AppProject,NodePool,EC2NodeClass
