#!/usr/bin/env python3
# Copyright (c) 2026 sin2503. MIT License.
# SPDX-License-Identifier: MIT
"""
20 画面・15000 行の nginx COMBINED 形式サンプルログを生成する。

- メインの PATHS は「クロールでサイトマップに載る想定」のパス。
- LOG_ONLY_PATHS はサイトマップに無いがログに残るパス（404 等のデモ用）。
- 同時に scripts/sample_sitemap_demo.json を出力する（PATHS のみ。解析時にこれを
  --sitemap で渡すと、遷移図は 20 画面のみ・下部に「ログにのみあるパス」が出る）。
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# クロール済み想定（サイトマップに載る）20 画面
PATHS = [
    "/",
    "/about",
    "/contact",
    "/products",
    "/page5", "/page6", "/page7", "/page8", "/page9", "/page10",
    "/page11", "/page12", "/page13", "/page14", "/page15",
    "/page16", "/page17", "/page18", "/page19", "/page20",
]

# サイトマップに無いがアクセスログには現れるパス（旧 URL・未リンク・404 想定）
LOG_ONLY_PATHS = [
    "/old-promo-2023",
    "/removed-product",
    "/api/legacy/v1/gone",
    "/never-linked-page",
    "/wp-login.php",
    "/feed.xml.bak",
]

LOG_ONLY_PATH_SET = frozenset(LOG_ONLY_PATHS)

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


def pick_path() -> str:
    """約 12% はサイトマップ外パス（デモ用）。"""
    if random.random() < 0.12:
        return random.choice(LOG_ONLY_PATHS)
    return random.choice(PATHS)


def pick_status(path: str) -> int:
    if path in LOG_ONLY_PATH_SET:
        return random.choices([404, 403, 301, 200], weights=[68, 8, 7, 17])[0]
    return random.choices([200, 200, 200, 304, 404], weights=[85, 10, 2, 2, 1])[0]


def write_demo_sitemap(out_path: Path) -> None:
    """PATHS のみのサイトマップ JSON（遷移図カードと一致させる用）。"""
    data: dict[str, dict] = {}
    for p in PATHS:
        url = "https://example.com/" if p == "/" else f"https://example.com{p}"
        title = "Home" if p == "/" else f"Page {p.strip('/')}"
        data[p] = {"url": url, "path": p, "title": title, "links_out": []}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    out_path = repo_root / "sample_access.log"
    sitemap_demo_path = Path(__file__).resolve().parent / "sample_sitemap_demo.json"
    n_lines = 15_000
    n_ips = 80
    ips = [random_ip() for _ in range(n_ips)]

    # 各 IP で「現在のパス」を覚えてリファラをそれっぽくする
    current_path: dict[str, str] = {}

    lines = []
    t = BASE_TIME
    log_only_hits = 0
    for _ in range(n_lines):
        ip = random.choice(ips)
        path = pick_path()
        if path in LOG_ONLY_PATH_SET:
            log_only_hits += 1
        prev = current_path.get(ip, "-")
        if prev != "-":
            referer = f"https://example.com{prev}"
        else:
            referer = "-"
        current_path[ip] = path

        t = t + timedelta(seconds=random.randint(1, 120))
        status = pick_status(path)
        size = random.randint(500, 8000) if status == 200 else (0 if status == 304 else random.randint(200, 500))
        ua = random.choice(USER_AGENTS)

        line = (
            f'{ip} - - [{format_nginx_time(t)}] '
            f'"GET {path} HTTP/1.1" {status} {size} "{referer}" "{ua}"'
        )
        lines.append(line)

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_demo_sitemap(sitemap_demo_path)
    print(f"Wrote {len(lines)} lines to {out_path}")
    print(f"Wrote demo sitemap ({len(PATHS)} paths) to {sitemap_demo_path}")
    print(f"Log-only path requests in this run: {log_only_hits} (~12% target). Use --sitemap {sitemap_demo_path} to see them under the transition diagram.")


if __name__ == "__main__":
    main()
