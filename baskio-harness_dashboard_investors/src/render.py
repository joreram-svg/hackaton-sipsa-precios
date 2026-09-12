"""Injects the computed dataset into the static Baskio template."""
import json
from pathlib import Path

PLACEHOLDER = "__BASKIO_DATA_JSON__"


def render_html(template_path: Path, dataset: dict) -> str:
    template = template_path.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise RuntimeError(f"Template is missing the {PLACEHOLDER} placeholder — did it get edited by hand?")
    blob = json.dumps(dataset, ensure_ascii=False)
    return template.replace(PLACEHOLDER, blob, 1)
