from __future__ import annotations

import base64
import io
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "compose"))

from media_providers import CommonsRetriever, OpenAIImageProvider, ProviderFailure  # noqa: E402


SECRET = "provider-test-secret"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, *, headers=None, chunks=()):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self._chunks = list(chunks)
        self.closed = False

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


class FakeSession:
    def __init__(self, *, post_response=None, get_response=None, post_error=None):
        self.trust_env = True
        self.headers = requests.structures.CaseInsensitiveDict()
        self.post_response = post_response
        self.get_response = get_response
        self.post_error = post_error
        self.post = Mock(side_effect=self._post)
        self.get = Mock(side_effect=self._get)
        self.close = Mock()

    def _post(self, *args, **kwargs):
        if self.post_error:
            raise self.post_error
        return self.post_response

    def _get(self, *args, **kwargs):
        return self.get_response


def png_bytes():
    out = io.BytesIO()
    Image.new("RGB", (2, 3), (12, 34, 56)).save(out, format="PNG")
    return out.getvalue()


def openai_response(data: bytes, *, status=200, headers=None):
    return FakeResponse(status, {"data": [{"b64_json": base64.b64encode(data).decode("ascii")}],
                                 "usage": {"input_tokens": 1}}, headers=headers)


def test_openai_timeout_is_ambiguous_and_never_retried_or_leaked():
    session = FakeSession(post_error=requests.Timeout(f"timeout for {SECRET} prompt"))
    provider = OpenAIImageProvider(SECRET, session=session)
    assert session.trust_env is False
    with pytest.raises(ProviderFailure) as caught:
        provider.generate("synthetic request")
    assert session.post.call_count == 1
    assert SECRET not in str(caught.value)
    assert "synthetic request" not in str(caught.value)


def test_openai_redirect_is_not_followed_and_key_is_not_in_error():
    session = FakeSession(post_response=FakeResponse(
        302, {"error": SECRET}, headers={"Location": "https://attacker.invalid/collect"}))
    provider = OpenAIImageProvider(SECRET, session=session)
    with pytest.raises(ProviderFailure) as caught:
        provider.generate("synthetic request")
    assert session.post.call_count == 1
    assert session.post.call_args.kwargs["allow_redirects"] is False
    assert session.post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {SECRET}"
    assert SECRET not in str(caught.value)


def test_openai_provider_accepts_valid_image_and_bounds_response():
    image = png_bytes()
    session = FakeSession(post_response=openai_response(image, headers={"x-request-id": "offline-test"}))
    result = OpenAIImageProvider(SECRET, session=session).generate("synthetic request")
    assert result["data"] == image
    assert result["request_id"] == "offline-test"
    assert result["source"]["provider"] == "openai"
    assert session.post.call_count == 1
    assert session.post.call_args.kwargs["allow_redirects"] is False
    assert session.post.call_args.kwargs['json'] == {
        'model': 'gpt-image-2.5-sunburst', 'prompt': 'synthetic request',
        'size': '1024x1024', 'quality': 'high', 'n': 1}


def test_openai_rejects_unsupported_options_before_post():
    session = FakeSession()
    with pytest.raises(ValueError):
        OpenAIImageProvider(SECRET, session=session).generate('Synthetic brief', options={'aspect_ratio': '3:4'})
    session.post.assert_not_called()


@pytest.mark.parametrize("encoded", ["%%%not-base64%%%", base64.b64encode(b"not an image").decode("ascii")])
def test_openai_rejects_malformed_or_non_image_bytes(encoded):
    session = FakeSession(post_response=FakeResponse(200, {"data": [{"b64_json": encoded}]}))
    with pytest.raises(ProviderFailure):
        OpenAIImageProvider(SECRET, session=session).generate("synthetic request")


def test_openai_rejects_decoded_image_over_20_mib():
    oversized = b"x" * (20 * 1024 * 1024 + 1)
    session = FakeSession(post_response=FakeResponse(
        200, {"data": [{"b64_json": base64.b64encode(oversized).decode("ascii")}]}))
    with pytest.raises(ProviderFailure):
        OpenAIImageProvider(SECRET, session=session).generate("synthetic request")


def test_commons_download_requires_explicit_rights_acknowledgement_without_network():
    session = FakeSession(get_response=FakeResponse(200, chunks=[png_bytes()]))
    retriever = CommonsRetriever(session=session)
    candidate = {"download_url": "https://upload.wikimedia.org/example/image.png"}
    with pytest.raises(ValueError, match="acknowledge"):
        retriever.download(candidate, rights_acknowledged=False)
    session.get.assert_not_called()


@pytest.mark.parametrize("url", [
    "http://upload.wikimedia.org/example/image.png",
    "https://upload.wikimedia.org.evil.invalid/example/image.png",
    "https://user:pass@upload.wikimedia.org/example/image.png",
    "https://example.invalid/upload.wikimedia.org/image.png",
])
def test_commons_rejects_non_https_or_non_wikimedia_download_hosts(url):
    session = FakeSession(get_response=FakeResponse(200, chunks=[png_bytes()]))
    retriever = CommonsRetriever(session=session)
    with pytest.raises(ValueError, match="Only selected Wikimedia"):
        retriever.download({"download_url": url}, rights_acknowledged=True)
    session.get.assert_not_called()


def test_commons_download_uses_https_wikimedia_and_bounded_no_redirect_request():
    image = png_bytes()
    response = FakeResponse(200, chunks=[image[:8], image[8:]])
    session = FakeSession(get_response=response)
    retriever = CommonsRetriever(session=session)
    result = retriever.download(
        {"download_url": "https://upload.wikimedia.org/wikipedia/commons/test.png"},
        rights_acknowledged=True,
    )
    assert result == image
    session.get.assert_called_once_with(
        "https://upload.wikimedia.org/wikipedia/commons/test.png",
        stream=True,
        timeout=(5, 30),
        allow_redirects=False,
    )
    assert response.closed


def test_commons_download_rejects_oversized_stream():
    response = FakeResponse(200, chunks=[b"x" * (20 * 1024 * 1024 + 1)])
    session = FakeSession(get_response=response)
    retriever = CommonsRetriever(session=session)
    with pytest.raises(ValueError, match="20 MiB"):
        retriever.download(
            {"download_url": "https://upload.wikimedia.org/wikipedia/commons/large.png"},
            rights_acknowledged=True,
        )
    assert response.closed
