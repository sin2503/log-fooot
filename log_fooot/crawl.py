# Copyright (c) 2026 sin2503. MIT License.
# SPDX-License-Identifier: MIT
"""
指定した Web サイトをクロールし、URL 一覧と画面構成（パス・タイトル）を取得するモジュール。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import unquote, urljoin, urlparse, urlunparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup


@dataclass
class PageInfo:
    """1ページの情報。"""

    url: str
    path: str
    title: str
    links_out: list[str] = field(default_factory=list)


def _normalize_url(base: str, url: str) -> str:
    """URL を絶対化し、フラグメントを除いて正規化する。"""
    u = urljoin(base, url)
    parsed = urlparse(u)
    # フラグメント除去
    normalized = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, "")
    )
    return normalized


def _same_origin(base_netloc: str, url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == base_netloc or (parsed.netloc == "" and url.startswith("/"))


def _path_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    try:
        path = unquote(path, encoding="utf-8")
    except Exception:
        pass
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path


def crawl(
    base_url: str,
    max_pages: int = 500,
    delay_seconds: float = 0.5,
    timeout: int = 10,
    headers: dict | None = None,
) -> dict[str, PageInfo]:
    """
    指定した base_url から同一オリジン内のリンクを辿り、ページ情報を収集する。

    Returns:
        path -> PageInfo の辞書（path は / 始まりの正規化パス）
    """
    base_parsed = urlparse(base_url)
    base_netloc = base_parsed.netloc
    base_scheme = base_parsed.scheme or "https"

    default_headers = {
        "User-Agent": "log-fooot/0.1 (nginx log analyzer; +https://github.com)",
    }
    if headers:
        default_headers.update(headers)

    seen: set[str] = set()
    by_path: dict[str, PageInfo] = {}
    to_visit: list[str] = [urljoin(base_url, "/")]

    while to_visit and len(by_path) < max_pages:
        url = to_visit.pop(0)
        if url in seen:
            continue
        seen.add(url)

        path = _path_from_url(url)
        if path in by_path:
            continue

        try:
            resp = requests.get(
                url,
                headers=default_headers,
                timeout=timeout,
                allow_redirects=True,
            )
            resp.raise_for_status()
        except requests.RequestException:
            by_path[path] = PageInfo(url=url, path=path, title="(fetch failed)", links_out=[])
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        title_tag = soup.find("title")
        title = (title_tag.get_text(strip=True) if title_tag else "") or path or "/"

        links_out: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            absolute = _normalize_url(url, href)
            if not _same_origin(base_netloc, absolute):
                continue
            absolute_path = _path_from_url(absolute)
            full_url = urljoin(base_url, absolute_path)
            links_out.append(absolute_path)
            if full_url not in seen and absolute_path not in by_path:
                to_visit.append(full_url)

        by_path[path] = PageInfo(url=url, path=path, title=title, links_out=links_out)

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return by_path
