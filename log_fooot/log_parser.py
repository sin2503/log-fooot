"""
nginx COMBINED 形式のアクセスログをパースするモジュール。

format: $remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


@dataclass
class LogEntry:
    """1行のログエントリ。"""

    ip: str
    time_local: datetime | None  # パース失敗時は None
    method: str
    path: str
    status: int
    body_bytes_sent: int
    referer: str
    user_agent: str
    raw: str


# COMBINED: 先頭部分 "IP - - [date] " の正規表現
_HEAD_RE = re.compile(
    r"^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"  # IP - - [time_local]
)
# リクエスト行は "METHOD PATH PROTOCOL"
_REQUEST_RE = re.compile(r"^(\S+)\s+(\S+)")
# 時刻パース (16/Mar/2025:10:00:00 +0000)
_STRPTIME_FMT = "%d/%b/%Y:%H:%M:%S %z"


def _parse_time(s: str) -> datetime | None:
    try:
        # スペースの前に : があるので、%z は +0000 のような形式
        return datetime.strptime(s.strip(), _STRPTIME_FMT)
    except ValueError:
        return None


def _parse_request(request_str: str) -> tuple[str, str]:
    m = _REQUEST_RE.match(request_str.strip())
    if m:
        return m.group(1), m.group(2)
    return "GET", ""


def parse_line(line: str) -> LogEntry | None:
    """
    1行の COMBINED ログをパースする。
    失敗した場合は None を返す。
    """
    line = line.rstrip("\n")
    if not line.strip():
        return None

    # ダブルクォートで分割: [0]=前半, [1]=request, [2]=status+bytes, [3]=referer, [4]=空白, [5]=user_agent
    parts = line.split('"')
    if len(parts) < 5:
        return None

    head = parts[0]
    request_str = parts[1].strip()
    middle = parts[2].strip().split()
    referer = parts[3].strip() if len(parts) > 3 else ""
    user_agent = parts[5].strip() if len(parts) > 5 else (parts[4].strip() if len(parts) > 4 else "")

    m = _HEAD_RE.match(head)
    if not m:
        return None

    ip = m.group(1)
    time_str = m.group(2)
    method, path = _parse_request(request_str)

    status = 0
    body_bytes_sent = 0
    if len(middle) >= 2:
        try:
            status = int(middle[0])
            body_bytes_sent = int(middle[1])
        except ValueError:
            pass

    return LogEntry(
        ip=ip,
        time_local=_parse_time(time_str),
        method=method,
        path=path,
        status=status,
        body_bytes_sent=body_bytes_sent,
        referer=referer,
        user_agent=user_agent,
        raw=line,
    )


def parse_file(log_path: str | Path) -> Iterator[LogEntry]:
    """ログファイルを開き、1行ずつパースして LogEntry を yield する。"""
    path = Path(log_path)
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            entry = parse_line(line)
            if entry is not None:
                yield entry
