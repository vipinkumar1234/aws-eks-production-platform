"""Write optional reviewed CI root inputs; never print their contents."""
import json
import os
from pathlib import Path

raw = os.getenv("ROOT_INPUTS", "")
if raw:
    values = json.loads(raw)
    if not isinstance(values, dict):
        raise SystemExit("TFVARS_JSON must be a JSON object")
    root = Path(os.environ["GITHUB_WORKSPACE"])
    # Jobs are isolated; each credentials job plans just one of these roots.
    for environment in ("dev", "prod"):
        path = root / "terraform/environments" / environment / "ci.auto.tfvars.json"
        path.write_text(json.dumps(values), encoding="utf-8")
