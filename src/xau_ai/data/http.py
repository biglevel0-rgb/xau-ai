"""Shared HTTP helper for REST data providers (stdlib only, injectable in tests)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from xau_ai.core.exceptions import DataProviderError


# Some feeds (e.g. faireconomy) reject urllib's default agent with HTTP 403.
_DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; xau-ai/0.1)"}


def get_json(
    url: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 15,
) -> Any:
    """GET ``url`` (with optional query/headers) and parse the JSON body."""
    full_url = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    request = urllib.request.Request(
        full_url, headers={**_DEFAULT_HEADERS, **(headers or {})}, method="GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise DataProviderError(f"HTTP {response.status} from {url}")
            payload = response.read()
    except urllib.error.URLError as exc:
        raise DataProviderError(f"request to {url} failed: {exc}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DataProviderError(f"non-JSON response from {url}") from exc
