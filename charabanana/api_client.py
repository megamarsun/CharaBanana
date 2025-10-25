"""NanoBanana API client wrapper."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

from .environment import EnvironmentPaths, ensure_dir
from .storage import DataStore

API_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash-image:generateContent"
)


@dataclass
class ApiResult:
    output_path: str
    test_status: int


class ApiClientError(Exception):
    """Raised when the API call fails."""

    def __init__(self, title: str, message: str, *, is_error: bool = True) -> None:
        super().__init__(message)
        self.title = title
        self.message = message
        self.is_error = is_error


def guess_mime_type(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    if lower.endswith(".bmp"):
        return "image/bmp"
    return "image/png"


def file_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def augment_prompt(user_text: str) -> str:
    guard = (
        "ゼロからの新規生成は禁止。最後の画像（ベース画像）を加工対象とし、"
        "構図・カメラ・照明・解像度・アスペクト比・被写体の形状を保持。"
        "他の参照画像は色味や質感などの雰囲気だけに使う。"
    )
    base = (user_text or "").strip()
    if base:
        return base + "\n" + guard
    return guard


class NanoBananaClient:
    """Client responsible for communicating with the NanoBanana API."""

    def __init__(self, datastore: DataStore, paths: EnvironmentPaths) -> None:
        self.datastore = datastore
        self.paths = paths

    def _build_parts(self, final_prompt: str, base_image: str, refs: Iterable[str]) -> List[dict]:
        parts = [{"text": augment_prompt(final_prompt)}]

        # Atmosphere references (up to 2)
        for refp in list(refs)[:2]:
            if os.path.isfile(refp):
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": guess_mime_type(refp),
                            "data": file_to_b64(refp),
                        }
                    }
                )

        # Base image (last)
        parts.append(
            {
                "inline_data": {
                    "mime_type": guess_mime_type(base_image),
                    "data": file_to_b64(base_image),
                }
            }
        )
        return parts

    def _build_generation_config(self, aspect_ratio: str) -> dict:
        config = {"responseModalities": ["Image"]}
        if aspect_ratio and aspect_ratio != "自動":
            config["imageConfig"] = {"aspectRatio": aspect_ratio}
        return config

    def generate_image(
        self,
        *,
        api_key: str,
        final_prompt: str,
        base_image: str,
        ref_images: Iterable[str],
        aspect_ratio: str,
    ) -> ApiResult:
        if not api_key:
            raise ApiClientError("エラー", "APIキーが未設定です 設定タブで保存してね")

        if not os.path.isfile(base_image):
            raise ApiClientError("エラー", "ベース画像のファイルが存在しないよ")

        import requests

        parts = self._build_parts(final_prompt, base_image, ref_images)
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": self._build_generation_config(aspect_ratio),
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        ca_path = self.paths.ca_bundle if self.paths.ca_bundle else True

        test_url = "https://generativelanguage.googleapis.com/"
        try:
            response_test = requests.get(test_url, timeout=5, verify=ca_path)
            test_status = response_test.status_code
        except Exception as exc:  # pragma: no cover - GUI feedback
            raise ApiClientError(
                "通信テスト失敗",
                "exeがHTTPS接続できなかったよ\n"
                f"証明書ファイル: {self.paths.ca_bundle}\n"
                f"URL: {test_url}\n"
                f"例外: {exc}\n\n"
                "セキュリティソフトやFWがexeの外向き通信を止めてる可能性が高い",
            ) from exc

        try:
            response = requests.post(
                API_ENDPOINT,
                headers=headers,
                json=body,
                timeout=180,
                verify=ca_path,
            )
        except requests.exceptions.RequestException as exc:  # pragma: no cover - GUI feedback
            raise ApiClientError(
                "送信失敗",
                "HTTPエラー(POSTできなかった)\n"
                f"証明書ファイル: {self.paths.ca_bundle}\n"
                "ステップ: POST\n"
                f"例外: {exc}",
            ) from exc

        status = response.status_code
        if status == 429:
            raise ApiClientError(
                "送信失敗",
                "429 レート制限 or 無料枠上限\n"
                f"{response.text[:500]}",
            )
        if status != 200:
            raise ApiClientError(
                "送信失敗",
                f"ステータス {status}\n"
                f"証明書ファイル: {self.paths.ca_bundle}\n"
                f"レスポンス: {response.text[:500]}",
            )

        try:
            resp_json = response.json()
        except Exception as exc:
            raise ApiClientError(
                "解析失敗",
                "サーバーからJSONじゃないものが返ってきた\n"
                f"{exc}\n"
                f"{response.text[:500]}",
            ) from exc

        if isinstance(resp_json, dict) and "error" in resp_json:
            err = resp_json["error"]
            code = err.get("code")
            status_txt = err.get("status")
            message = err.get("message", "Unknown error")
            raise ApiClientError(
                "送信失敗",
                f"APIエラー: {code}/{status_txt}\n{message}",
            )

        img_b64: Optional[str] = None
        try:
            parts_out = resp_json["candidates"][0]["content"]["parts"]
            for part in parts_out:
                data_obj = part.get("inline_data") or part.get("inlineData")
                if data_obj and "data" in data_obj:
                    img_b64 = data_obj["data"]
                    break
        except Exception:
            img_b64 = None

        if not img_b64:
            ensure_dir(self.paths.output_dir)
            debug_path = os.path.join(self.paths.output_dir, "last_response.json")
            with open(debug_path, "w", encoding="utf-8") as debug_file:
                json.dump(resp_json, debug_file, ensure_ascii=False, indent=2)
            preview_head = json.dumps(resp_json, ensure_ascii=False)[:800]
            raise ApiClientError(
                "完了",
                "レスポンスに画像データが見つからなかった\n"
                f"{debug_path} を確認して\n\n"
                f"{preview_head}",
                is_error=False,
            )

        ensure_dir(self.paths.output_dir)
        gallery = self.datastore.load_gallery()
        next_index = len(gallery) + 1
        out_name = f"img_{next_index:04d}.png"
        out_path = os.path.join(self.paths.output_dir, out_name)

        with open(out_path, "wb") as image_file:
            image_file.write(base64.b64decode(img_b64))

        gallery.append({"file": out_path, "prompt": final_prompt})
        self.datastore.save_gallery(gallery)

        return ApiResult(output_path=out_path, test_status=test_status)
