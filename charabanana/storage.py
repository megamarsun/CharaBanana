"""JSON storage helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from .environment import EnvironmentPaths, ensure_dir


@dataclass
class DataStore:
    """Wrapper around application data files."""

    paths: EnvironmentPaths

    def _load(self, path: str, default: Any) -> Any:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self._write(path, default)
            return default

    def _write(self, path: str, data: Any) -> None:
        ensure_dir(self.paths.data_dir)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # Characters ---------------------------------------------------------
    def load_characters(self) -> Dict[str, Any]:
        return self._load(self.paths.characters_file, {})

    def save_characters(self, data: Dict[str, Any]) -> None:
        self._write(self.paths.characters_file, data)

    # Config -------------------------------------------------------------
    def load_config(self) -> Dict[str, Any]:
        return self._load(self.paths.config_file, {"apiKey": ""})

    def save_config(self, data: Dict[str, Any]) -> None:
        self._write(self.paths.config_file, data)

    # Gallery ------------------------------------------------------------
    def load_gallery(self) -> List[Dict[str, Any]]:
        return self._load(self.paths.gallery_file, [])

    def save_gallery(self, data: List[Dict[str, Any]]) -> None:
        self._write(self.paths.gallery_file, data)

    # Scripts ------------------------------------------------------------
    def load_scripts(self) -> List[Dict[str, Any]]:
        return self._load(self.paths.scripts_file, [])

    def save_scripts(self, data: List[Dict[str, Any]]) -> None:
        self._write(self.paths.scripts_file, data)
