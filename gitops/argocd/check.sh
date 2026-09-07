#!/usr/bin/env bash
set -euo pipefail
command -v kubeconform >/dev/null || { echo 'kubeconform is required'; exit 1; }
kubeconform -strict -summary bootstrap projects
