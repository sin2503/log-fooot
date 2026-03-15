# Copyright (c) 2026 sin2503. MIT License.
# SPDX-License-Identifier: MIT
"""
ログエントリを IP ごとにまとめ、セッション（遷移パス）を構築するモジュール。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote

from .log_parser import LogEntry, parse_file


@dataclass
class Step:
    """1ステップ（1リクエスト）。"""

    path: str
    time: datetime | None
    status: int
    referer: str
    user_agent: str = ""


@dataclass
class Session:
    """1つのセッション（同一 IP の連続したアクセス）。"""

    ip: str
    steps: list[Step] = field(default_factory=list)


def _normalize_path(path: str) -> str:
    """ログの path を正規化（クエリは捨てる）。percent エンコードは UTF-8 でデコードする。"""
    if "?" in path:
        path = path.split("?")[0]
    path = path or "/"
    try:
        path = unquote(path, encoding="utf-8")
    except Exception:
        pass
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path


def build_sessions(
    log_path: str,
    session_gap_minutes: int = 30,
    base_netloc: str = "",
    only_html: bool = True,
    exclude_ips: set[str] | None = None,
) -> list[Session]:
    """
    ログファイルを読み、IP ごとに時系列で並べ、セッションに分割する。

    Args:
        log_path: ログファイルパス
        session_gap_minutes: 同一 IP でこの分数以上空いたら別セッション
        base_netloc: 対象サイトのホスト（空の場合は全パスを対象）
        only_html: True のとき .js/.css/.png 等は無視（パスで判定）
        exclude_ips: 除外する IP の集合。これらの IP のセッションは集計に含めない。

    Returns:
        セッションのリスト
    """
    # 静的リソースっぽい拡張子はスキップ（only_html 時）
    SKIP_EXT = (
        ".js",
        ".css",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".map",
    )

    by_ip: dict[str, list[LogEntry]] = {}
    for entry in parse_file(log_path):
        path = _normalize_path(entry.path)
        if only_html:
            path_lower = path.lower()
            if any(path_lower.endswith(ext) for ext in SKIP_EXT):
                continue
        if entry.status >= 400 and only_html:
            continue
        if entry.time_local is None:
            continue
        by_ip.setdefault(entry.ip, []).append(entry)

    if exclude_ips is None:
        exclude_ips = set()

    sessions: list[Session] = []
    for ip, entries in by_ip.items():
        if ip in exclude_ips:
            continue
        entries.sort(key=lambda e: (e.time_local or datetime.min))
        gap_seconds = session_gap_minutes * 60
        current: list[Step] = []
        prev_time: datetime | None = None

        for e in entries:
            t = e.time_local
            if prev_time is not None and t is not None and (t - prev_time).total_seconds() > gap_seconds:
                if current:
                    sessions.append(Session(ip=ip, steps=current))
                current = []
            current.append(
                Step(
                    path=_normalize_path(e.path),
                    time=t,
                    status=e.status,
                    referer=e.referer or "",
                    user_agent=e.user_agent or "",
                )
            )
            prev_time = t
        if current:
            sessions.append(Session(ip=ip, steps=current))

    return sessions
