# Copyright (c) 2026 sin2503. MIT License.
# SPDX-License-Identifier: MIT
"""
指定した Web サイトをクロールし、URL 一覧と画面構成（パス・タイトル）を取得するモジュール。
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from urllib.parse import unquote, urljoin, urlparse, urlunparse
from pathlib import Path

from .exclude_paths import is_excluded_path


@dataclass
class PageInfo:
    """1ページの情報。"""

    url: str
    path: str
    title: str
    links_out: list[str] = field(default_factory=list)


def _normalize_url(base: str, url: str) -> str:
    """URL を絶対化し、フラグメントを除いて正規化する。

    相対リンク解決のため、base がディレクトリなら末尾 `/` を維持したまま
    urljoin する（`/ft8` + `howto/` → `/howto/` になるのを防ぐ）。
    """
    u = urljoin(base, url)
    parsed = urlparse(u)
    # フラグメント除去（path の末尾 `/` は維持）
    normalized = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, "")
    )
    return normalized


def _same_origin(base_netloc: str, url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == base_netloc or (parsed.netloc == "" and url.startswith("/"))


def _directory_base_url(url: str) -> str:
    """
    相対リンク解決用に、URL をディレクトリとして扱う形にする。

    `/ft8` のように末尾スラッシュが無いと urljoin はファイル扱いし、
    `howto/` が `/howto/` に潰れる。パスに拡張子が無い場合は `/` を付ける。
    """
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path.endswith("/") or path == "/":
        return url
    last = path.rsplit("/", 1)[-1]
    if "." in last:
        # /page.html のようなファイル URL はそのまま
        return url
    return urlunparse(
        (parsed.scheme, parsed.netloc, path + "/", parsed.params, parsed.query, parsed.fragment)
    )


def _soup_from_response_text(text: str):
    """
    html.parser でパースする。XML（sitemap.xml 等）が混ざると BS4 が警告を出すが、
    リンク抽出用途では問題にならないためその警告だけ抑止する。
    """
    from bs4 import BeautifulSoup

    try:
        from bs4 import XMLParsedAsHTMLWarning
    except ImportError:  # 古い beautifulsoup4
        XMLParsedAsHTMLWarning = None  # type: ignore[misc, assignment]

    if XMLParsedAsHTMLWarning is not None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
            return BeautifulSoup(text, "html.parser")
    return BeautifulSoup(text, "html.parser")


def _html_text_from_response(resp) -> str:
    """
    レスポンス本文を HTML 文字列にする。

    Content-Type の charset が latin-1 / ISO-8859-1 でも、実体が UTF-8 の
    サイトが多い。httpx の resp.text だと誤デコードで文字化けするため、
    UTF-8 を優先し、失敗時のみヘッダの charset にフォールバックする。
    """
    content = getattr(resp, "content", b"") or b""
    if not content:
        return ""
    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode("utf-8-sig")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    encoding = getattr(resp, "charset_encoding", None) or getattr(resp, "encoding", None) or "utf-8"
    try:
        return content.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        return content.decode("utf-8", errors="replace")


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
    exclude_paths: set[str] | None = None,
) -> dict[str, PageInfo]:
    """
    指定した base_url から同一オリジン内のリンクを辿り、ページ情報を収集する。

    Returns:
        path -> PageInfo の辞書（path は / 始まりの正規化パス）
    """
    import httpx

    base_parsed = urlparse(base_url)
    base_netloc = base_parsed.netloc

    default_headers = {
        "User-Agent": "log-fooot/0.1 (nginx log analyzer; +https://github.com)",
    }
    if headers:
        default_headers.update(headers)

    seen: set[str] = set()
    by_path: dict[str, PageInfo] = {}
    to_visit: list[str] = [urljoin(base_url, "/")]

    # http2=True: ALPN で HTTP/2 を優先（未対応なら HTTP/1.1 にフォールバック）
    with httpx.Client(
        http2=True,
        headers=default_headers,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        while to_visit and len(by_path) < max_pages:
            url = to_visit.pop(0)
            if url in seen:
                continue
            seen.add(url)

            path = _path_from_url(url)
            if exclude_paths and is_excluded_path(path, exclude_paths):
                continue
            if path in by_path:
                continue

            try:
                resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                code = e.response.status_code if e.response is not None else "?"
                by_path[path] = PageInfo(
                    url=url, path=path, title=f"(fetch failed: {code})", links_out=[]
                )
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
                continue
            except httpx.HTTPError:
                by_path[path] = PageInfo(url=url, path=path, title="(fetch failed)", links_out=[])
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
                continue

            # リダイレクト後 URL を基準にする（/ft8 → /ft8/ など）
            page_url = str(resp.url)
            seen.add(page_url)
            path = _path_from_url(page_url)
            if exclude_paths and is_excluded_path(path, exclude_paths):
                continue
            if path in by_path:
                continue

            soup = _soup_from_response_text(_html_text_from_response(resp))
            title_tag = soup.find("title")
            title = (title_tag.get_text(strip=True) if title_tag else "") or path or "/"

            # 相対リンクはディレクトリ基準で解決（末尾 / 無しだと親パスが欠ける）
            link_base = _directory_base_url(page_url)
            links_out: list[str] = []
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                    continue
                absolute = _normalize_url(link_base, href)
                if not _same_origin(base_netloc, absolute):
                    continue
                absolute_path = _path_from_url(absolute)
                if exclude_paths and is_excluded_path(absolute_path, exclude_paths):
                    continue
                links_out.append(absolute_path)
                # path を付け直さず、正規化済み絶対 URL をそのまま辿る（末尾 / を維持）
                if absolute not in seen and absolute_path not in by_path:
                    to_visit.append(absolute)

            # 出現順を保ったまま重複除去
            links_out = list(dict.fromkeys(links_out))
            by_path[path] = PageInfo(url=page_url, path=path, title=title, links_out=links_out)

            if delay_seconds > 0:
                time.sleep(delay_seconds)

    return by_path
