"""Script processing utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .storage import DataStore


class ScriptProcessingError(Exception):
    """Raised when the script text cannot be processed."""


@dataclass
class ScriptProcessingResult:
    used_characters: List[str]
    replaced_text: str
    ref_slots: List[str]


def process_script(text: str, datastore: DataStore, save_new: bool) -> ScriptProcessingResult:
    db = datastore.load_characters()

    found = [name for name in db.keys() if name and name in text]

    if not found:
        raise ScriptProcessingError("登録済みキャラが見つからん")

    if len(found) > 3:
        raise ScriptProcessingError(
            f"このシーンは{len(found)}人います: {', '.join(found)}\n3人までに分けて"
        )

    replaced_text = text
    found_sorted = sorted(found, key=len, reverse=True)

    for cname in found_sorted:
        base_prompt_full = db[cname].get("basePrompt", "")
        short_desc = base_prompt_full.splitlines()[0] if base_prompt_full else cname
        token = f"[{short_desc}]"
        replaced_text = replaced_text.replace(cname, token)

    ref_slots: List[str] = []
    for cname in found_sorted:
        refs = db[cname].get("refs", [])
        if refs:
            ref_slots.append(refs[0])
        if len(ref_slots) >= 3:
            break

    if save_new:
        scripts = datastore.load_scripts()
        scripts.append({"script": text, "prompt": replaced_text})
        datastore.save_scripts(scripts)

    return ScriptProcessingResult(
        used_characters=found,
        replaced_text=replaced_text,
        ref_slots=ref_slots,
    )
