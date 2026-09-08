#!/usr/bin/env bash
set -euo pipefail
terraform fmt -check -recursive .
terraform validate
