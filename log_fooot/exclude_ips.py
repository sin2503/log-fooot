"""
除外 IP リストの読み書き。サーバ側（レポート作成時）で保持し集計から除外する。
"""

from __future__ import annotations

import csv
from pathlib import Path


def load_exclude_ips(path: str | Path) -> set[str]:
    """
    ファイルから除外 IP の集合を読み込む。
    - .txt: 1行1IP（# 以降は無視）
    - .csv: 1列目を IP として読み（ヘッダー行は1行目が数値で始まらなければスキップ）

    Returns:
        除外する IP の set（空白行・空は除く）
    """
    path = Path(path)
    if not path.exists():
        return set()

    ips: set[str] = set()
    suffix = path.suffix.lower()

    if suffix == ".csv":
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            try:
                reader = csv.reader(f)
                for row in reader:
                    if not row:
                        continue
                    cell = row[0].strip()
                    if not cell or cell.startswith("#"):
                        continue
                    # ヘッダーっぽい行はスキップ（先頭が数字なら IP の可能性）
                    if reader.line_num == 1 and cell and not cell[0].isdigit() and "." not in cell[:4]:
                        continue
                    ips.add(cell)
            except Exception:
                pass
        return ips

    # .txt またはその他
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                ips.add(line)
    return ips


def save_exclude_ips(path: str | Path, ips: set[str] | list[str]) -> None:
    """除外 IP を CSV で保存する（1列目に IP）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ip"])
        for ip in sorted(ips):
            w.writerow([ip])
