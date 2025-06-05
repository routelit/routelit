import json
from importlib import resources
from typing import Any, Dict

from .domain import ViteComponentsAssets


def get_vite_manifest(package_name: str) -> Dict[str, Any]:
    try:
        manifest_path = resources.files(package_name) / "static" / ".vite" / "manifest.json"

        if manifest_path.is_file():
            with manifest_path.open() as f:
                manifest_data = json.load(f)
                if isinstance(manifest_data, dict):
                    return manifest_data
    except (FileNotFoundError, AttributeError):
        pass
    return {}


def get_vite_components_assets(package_name: str) -> ViteComponentsAssets:
    manifest = get_vite_manifest(package_name)
    js_files = []
    css_files = []
    for source in manifest.values():
        filename = source["file"]
        if filename.endswith(".js"):
            js_files.append(filename)
        elif filename.endswith(".css"):
            css_files.append(filename)
        _css_files = source.get("css", [])
        for css_file in _css_files:
            css_files.append(css_file)
    return ViteComponentsAssets(
        package_name=package_name,
        js_files=js_files,
        css_files=css_files,
    )
