#!/usr/bin/env bash
set -euo pipefail
python -c "import yaml; yaml.safe_load(open('nodepool.yaml'))" 2>/dev/null || true
