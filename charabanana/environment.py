"""Environment setup utilities for CharaBanana."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import certifi


@dataclass(frozen=True)
class EnvironmentPaths:
    """Paths used by the application."""

    base_dir: str
    data_dir: str
    output_dir: str
    characters_file: str
    config_file: str
    gallery_file: str
    scripts_file: str
    ca_bundle: str


def _detect_base_dir() -> str:
    """Return the directory of the running application."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.dirname(os.path.abspath(__file__))


def ensure_dir(path: str) -> None:
    """Create a directory if it does not exist."""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def _ensure_data_files(data_dir: str) -> None:
    """Ensure that the base JSON files exist inside *data_dir*."""
    ensure_dir(data_dir)
    outputs_dir = os.path.join(data_dir, "outputs")
    ensure_dir(outputs_dir)

    _write_json_if_missing(
        os.path.join(data_dir, "config.json"), {"apiKey": "", "localSaveDir": ""}
    )
    _write_json_if_missing(os.path.join(data_dir, "characters.json"), {})
    _write_json_if_missing(os.path.join(data_dir, "gallery.json"), [])
    _write_json_if_missing(os.path.join(data_dir, "scripts.json"), [])


def _write_json_if_missing(path: str, default):
    if os.path.exists(path):
        return
    ensure_dir(os.path.dirname(path))
    import json

    with open(path, "w", encoding="utf-8") as f:
        json.dump(default, f, ensure_ascii=False, indent=2)


def _setup_ca_bundle(base_dir: str) -> str:
    """Setup CA bundle env vars and return the bundle path."""
    ca_path = certifi.where()
    if getattr(sys, "frozen", False):
        bundled = os.path.join(base_dir, "certifi", "cacert.pem")
        if os.path.exists(bundled):
            ca_path = bundled
    os.environ["REQUESTS_CA_BUNDLE"] = ca_path
    os.environ["SSL_CERT_FILE"] = ca_path
    return ca_path


def initialise_environment() -> EnvironmentPaths:
    """Create directories, configure certificates and return paths."""
    base_dir = _detect_base_dir()
    if getattr(sys, "frozen", False):
        data_dir = base_dir
    else:
        data_dir = os.path.join(base_dir, "data_work")
    _ensure_data_files(data_dir)

    output_dir = os.path.join(data_dir, "outputs")
    ca_bundle = _setup_ca_bundle(base_dir)

    return EnvironmentPaths(
        base_dir=base_dir,
        data_dir=data_dir,
        output_dir=output_dir,
        characters_file=os.path.join(data_dir, "characters.json"),
        config_file=os.path.join(data_dir, "config.json"),
        gallery_file=os.path.join(data_dir, "gallery.json"),
        scripts_file=os.path.join(data_dir, "scripts.json"),
        ca_bundle=ca_bundle,
    )
