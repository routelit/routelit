import json
from importlib import resources
from .domain import ViteComponentsAssets


def get_vite_manifest(package_name: str):
    manifest_path = resources.files(package_name).joinpath("static", ".vite", "manifest.json")

    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
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
