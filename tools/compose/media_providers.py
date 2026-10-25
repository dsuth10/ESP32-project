"""Explicit image generation/edit and external retrieval adapters.

No provider operation retries itself. A timed-out paid request may have run.
"""
from __future__ import annotations

import base64
import io
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


def safe_identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}', value) else ''


def safe_usage(value):
    counters = {'total_input_tokens', 'total_output_tokens', 'total_cached_tokens', 'total_thought_tokens',
                'total_tool_use_tokens', 'total_tokens', 'input_tokens', 'output_tokens'}
    if not isinstance(value, dict):
        return {}
    return {key: amount for key, amount in value.items() if key in counters
            and type(amount) is int and 0 <= amount <= 10**12}


class ProviderFailure(RuntimeError):
    """A request failed after dispatch; its billing outcome may be unknown."""

    def __init__(self, message, *, receipt=None):
        super().__init__(message)
        self.receipt = receipt or {}


class OpenAIImageProvider:
    def __init__(self, api_key: str, model: str = "gpt-image-2.5-sunburst", *, session=None):
        if not api_key or not model:
            raise ValueError("Configure the image provider key and model first.")
        self.key, self.model = api_key, model
        self.session = session or requests.Session()
        self.session.trust_env = False

    def generate(self, prompt: str, *, parent: Path | None = None, options: dict | None = None, on_stage=None) -> dict:
        from image_provider_config import validate_options
        output = validate_options('openai', options)
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000:
            raise ValueError("Image instructions must contain 1–8000 characters.")
        headers = {"Authorization": "Bearer " + self.key}
        options = {"model": self.model, "prompt": prompt, "size": output['size'], "quality": output['quality'], "n": 1}
        receipt = {'provider': 'openai', 'requested_model': self.model, 'outcome': 'uncertain'}
        started = None
        try:
            if on_stage:on_stage('Requesting image')
            if parent is None:
                started = time.perf_counter()
                response = self.session.post("https://api.openai.com/v1/images/generations", headers=headers,
                                             json=options, timeout=(10, 240), allow_redirects=False)
            else:
                # Managed blobs have no extension: report the detected image MIME explicitly.
                from PIL import Image
                with Image.open(parent) as image:
                    mime = Image.MIME.get(image.format, "image/png")
                with parent.open("rb") as source:
                    started = time.perf_counter()
                    response = self.session.post("https://api.openai.com/v1/images/edits", headers=headers,
                                                 data=options, files={"image[]": ("reference", source, mime)},
                                                 timeout=(10, 240), allow_redirects=False)
            receipt.update(http_status=response.status_code,
                request_id=safe_identifier(response.headers.get('x-request-id', '')),
                round_trip_seconds=round(time.perf_counter()-started, 3))
            if not 200 <= response.status_code < 300:
                raise ProviderFailure("Image provider did not confirm a result. Review this attempt before retrying.", receipt=receipt)
            if on_stage:on_stage('Receiving image')
            result = response.json()
            receipt['usage'] = safe_usage(result.get('usage'))
            encoded = result["data"][0]["b64_json"]
            if not isinstance(encoded, str) or len(encoded) > 28_000_000:
                raise ValueError("Invalid image response")
            data = base64.b64decode(encoded, validate=True)
            if not data or len(data) > 20 * 1024 * 1024:
                raise ValueError("Invalid image response")
            from media_store import MediaStore
            mime, width, height = MediaStore._inspect(data)
            receipt.update(outcome='image_received', mime=mime, width=width, height=height)
            return {"data": data, "mime": mime, "source": {"provider": "openai", "model": self.model},
                    "usage": receipt['usage'], "request_id": receipt['request_id'], 'receipt': receipt}
        except ProviderFailure:
            raise
        except Exception:
            if started is not None:
                receipt.setdefault('round_trip_seconds', round(time.perf_counter()-started, 3))
            # Never echo HTTP bodies, prompts, keys or filenames to operational logs.
            raise ProviderFailure("Image outcome is uncertain. The attempt is retained for recovery; it will not retry automatically.", receipt=receipt) from None

    def close(self):
        self.session.close()


class CommonsRetriever:
    """Explicit Commons search; a result's visibility does not grant reuse rights."""
    API = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": "ESP32ClassroomCompanion/0.2 (teacher-selected media lookup)"})

    def search(self, query: str) -> list[dict]:
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            raise ValueError("Enter a search of 1–200 characters.")
        response = self.session.get(self.API, params={"action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size"},
            timeout=(5, 20), allow_redirects=False)
        response.raise_for_status()
        candidates = []
        for page in response.json().get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            if info.get("mime") not in {"image/png", "image/jpeg", "image/webp"}:
                continue
            meta = info.get("extmetadata", {})
            # Metadata values may contain HTML; display as plain text, never execute markup.
            import re, html
            plain = lambda name: html.unescape(re.sub(r"<[^>]*>", "", str(meta.get(name, {}).get("value", ""))))[:2000]
            # Keep a bounded rights record for the Board's stricter automatic
            # reuse policy. The ordinary image workflow still asks the teacher
            # to review terms; presence of these fields grants no permission.
            rights_fields = ('LicenseShortName', 'LicenseUrl', 'UsageTerms', 'Copyrighted',
                             'AttributionRequired', 'Restrictions', 'Artist', 'Attribution',
                             'ObjectName', 'Credit', 'Permission', 'Copyright')
            rights = {name: {'value': plain(name)} for name in rights_fields if name in meta}
            candidates.append({"title": str(page.get("title", ""))[:200], "download_url": info.get("url", ""),
                "rights_metadata": rights,
                "source": {"url": info.get("descriptionurl", ""), "creator": plain("Artist"),
                           "licence": plain("LicenseShortName"), "attribution": plain("Attribution")}})
        return candidates

    def download(self, candidate: dict, *, rights_acknowledged: bool = False) -> bytes:
        if not rights_acknowledged:
            raise ValueError("Review and acknowledge the source's reuse terms before importing.")
        url = candidate.get("download_url", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "upload.wikimedia.org" or parsed.username or parsed.password:
            raise ValueError("Only selected Wikimedia image downloads are supported.")
        with self.session.get(url, stream=True, timeout=(5, 30), allow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError("The selected image could not be downloaded.")
            data = io.BytesIO()
            for chunk in response.iter_content(64 * 1024):
                if data.tell() + len(chunk) > 20 * 1024 * 1024:
                    raise ValueError("The image exceeds the 20 MiB import limit.")
                data.write(chunk)
            return data.getvalue()

    def close(self):
        self.session.close()
