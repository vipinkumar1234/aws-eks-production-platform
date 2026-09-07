#!/usr/bin/env bash
set -euo pipefail
python -m unittest discover -s tests -v
command -v trivy >/dev/null || { echo 'trivy is required'; exit 1; }
trivy config . --severity HIGH,CRITICAL --exit-code 1
