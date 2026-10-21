"""Enforce on-computer model processing without proxy or redirect escape."""
from urllib.parse import urlsplit

import requests


def require_loopback_origin(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or
            parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or
            parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Local-only processing requires a loopback model endpoint.")
    return value


def local_request(method, url, **kwargs):
    require_loopback_origin(url)
    with requests.Session() as session:
        session.trust_env = False
        response = session.request(method, url, allow_redirects=False, **kwargs)
        if 300 <= response.status_code < 400:
            response.close()
            raise ValueError("Local model redirects are refused.")
        return response
