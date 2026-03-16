# Copyright (c) 2026 sin2503. MIT License.
# SPDX-License-Identifier: MIT
"""
除外パス/ファイルリストの読み書き。クロール時・可視化時の両方で利用する。
"""

from __future__ import annotations

import csv
from pathlib import Path


def load_exclude_paths(path: str | Path) -> set[str]:
    """
    ファイルから除外パスの集合を読み込む。
    - .txt: 1行1パス（# 以降は無視）
    - .csv: 1列目をパスとして読み（ヘッダー行は1行目が先頭 / で始まらなければスキップ）

    Returns:
        除外するパスの set（空白行・空は除く）
    """
    p = Path(path)
    if not p.exists():
        return set()

    paths: set[str] = set()
    suffix = p.suffix.lower()

    if suffix == ".csv":
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                cell = row[0].strip()
                if not cell or cell.startswith("#"):
                    continue
                # ヘッダーっぽい行はスキップ（先頭が / でなければパスではないとみなす）
                if reader.line_num == 1 and cell and not cell.startswith("/"):
                    continue
                paths.add(cell)
        return paths

    # .txt またはその他
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                paths.add(line)
    return paths


def save_exclude_paths(path: str | Path, patterns: set[str] | list[str]) -> None:
    """除外パスを CSV で保存する（1列目に path）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path"])
        for pat in sorted(patterns):
            w.writerow([pat])


def is_excluded_path(path: str, patterns: set[str] | list[str] | None) -> bool:
    """
    除外パス/ファイルパターンと照合する。
    - 完全一致: そのパス/ファイルのみ除外
    - プレフィックス一致: pat が /admin の場合、/admin/ 以下をすべて除外
    """
    if not patterns:
        return False
    for raw in patterns:
        pat = (raw or "").strip()
        if not pat:
            continue
        if pat != "/" and pat.endswith("/"):
            pat = pat.rstrip("/")
        if path == pat:
            return True
        if pat != "/" and path.startswith(pat + "/"):
            return True
    return False

