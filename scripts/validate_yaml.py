"""Parse YAML, reject duplicate keys, and check manifests separately from Helm values."""
from pathlib import Path
import yaml


class UniqueLoader(yaml.SafeLoader):
    pass


def mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
root = Path(__file__).resolve().parents[1]
files = list((root / "gitops").rglob("*.yaml")) + list((root / ".github/workflows").glob("*.yml"))
for path in files:
    for document in yaml.load_all(path.read_text(encoding="utf-8"), Loader=UniqueLoader):
        if not isinstance(document, dict):
            raise ValueError(f"Expected mapping in {path}")
        if "gitops" in path.parts and path.name != "values.yaml":
            for key in ("apiVersion", "kind", "metadata"):
                if key not in document:
                    raise ValueError(f"Missing {key} in {path}")
print(f"Parsed {len(files)} YAML files; no duplicate keys or missing manifest envelopes.")
