#!/usr/bin/env python3
# Copyright (c) 2026 sin2503. MIT License.
# SPDX-License-Identifier: MIT
"""
20 画面・15000 行の nginx COMBINED 形式サンプルログを生成する。
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

# 20 画面のパス
PATHS = [
    "/",
    "/about",
    "/contact",
    "/products",
    "/page5", "/page6", "/page7", "/page8", "/page9", "/page10",
    "/page11", "/page12", "/page13", "/page14", "/page15",
    "/page16", "/page17", "/page18", "/page19", "/page20",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
]

BASE_TIME = datetime(2025, 3, 14, 0, 0, 0)


def random_ip() -> str:
    if random.random() < 0.6:
        return f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
    if random.random() < 0.8:
        return f"10.0.{random.randint(0, 255)}.{random.randint(1, 254)}"
    return f"172.16.{random.randint(0, 255)}.{random.randint(1, 254)}"


def format_nginx_time(dt: datetime) -> str:
    return dt.strftime("%d/%b/%Y:%H:%M:%S +0000")


def main() -> None:
    out_path = Path(__file__).resolve().parent.parent / "sample_access.log"
    n_lines = 15_000
    n_ips = 80
    ips = [random_ip() for _ in range(n_ips)]

    # 各 IP で「現在のパス」を覚えてリファラをそれっぽくする
    current_path: dict[str, str] = {}

    lines = []
    t = BASE_TIME
    for _ in range(n_lines):
        ip = random.choice(ips)
        path = random.choice(PATHS)
        prev = current_path.get(ip, "-")
        if prev != "-":
            referer = f"https://example.com{prev}"
        else:
            referer = "-"
        current_path[ip] = path

        t = t + timedelta(seconds=random.randint(1, 120))
        status = random.choices([200, 200, 200, 304, 404], weights=[85, 10, 2, 2, 1])[0]
        size = random.randint(500, 8000) if status == 200 else (0 if status == 304 else random.randint(200, 500))
        ua = random.choice(USER_AGENTS)

        line = (
            f'{ip} - - [{format_nginx_time(t)}] '
            f'"GET {path} HTTP/1.1" {status} {size} "{referer}" "{ua}"'
        )
        lines.append(line)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} lines to {out_path}")


if __name__ == "__main__":
    main()
