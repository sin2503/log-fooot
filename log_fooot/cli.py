"""
log-fooot のコマンドラインインターフェース。
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .crawl import crawl, PageInfo
from .exclude_ips import load_exclude_ips
from .sessions import build_sessions
from .visualize import (
    load_sitemap_json,
    render_html,
    save_sitemap_json,
    save_sessions_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="log-fooot",
        description="nginx COMBINED ログを IP ごとに解析し、画面遷移をカードと線で可視化する",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    parser.add_argument(
        "--base-url",
        type=str,
        default="",
        help="クロール対象のベース URL（例: https://example.com）",
    )
    parser.add_argument(
        "--log-path",
        type=str,
        default="",
        help="nginx COMBINED ログファイルのパス（例: /var/log/nginx/access.log）",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./log-fooot-output",
        help="解析結果（sitemap.json, sessions.json, report.html）を書き出すディレクトリ",
    )
    parser.add_argument(
        "--output-sitemap",
        type=str,
        default="",
        help="sitemap の出力ファイル名またはパス（既定: <output-dir>/sitemap.json）",
    )
    parser.add_argument(
        "--output-sessions",
        type=str,
        default="",
        help="sessions の出力ファイル名またはパス（既定: <output-dir>/sessions.json）",
    )
    parser.add_argument(
        "--output-report",
        type=str,
        default="",
        help="レポート HTML の出力ファイル名またはパス（既定: <output-dir>/report.html）",
    )
    parser.add_argument(
        "--crawl-only",
        action="store_true",
        help="クロールのみ実行し、sitemap.json を出力して終了",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="既存の sitemap を使いログ解析のみ実行（--sitemap でパス指定）",
    )
    parser.add_argument(
        "--sitemap",
        type=str,
        default="",
        help="既存 sitemap JSON のパス（--analyze-only 時に使用）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=500,
        help="クロールする最大ページ数（既定: 500）",
    )
    parser.add_argument(
        "--session-gap-minutes",
        type=int,
        default=30,
        help="同一 IP でこの分数以上空いたら別セッションとする（既定: 30）",
    )
    parser.add_argument(
        "--exclude-ips",
        type=str,
        default="",
        help="除外する IP を列挙したファイル（.txt または .csv）。未指定で --output-dir に exclude_ips.csv があればそれを読む",
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=["en", "ja"],
        default="en",
        help="レポートの表示言語（既定: en）",
    )

    args = parser.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def _out_path(opt: str, default_name: str) -> Path:
        if not opt.strip():
            return out_dir / default_name
        s = opt.strip()
        p = Path(s)
        if p.is_absolute():
            return p
        if "/" in s or "\\" in s:
            return p.resolve()
        return out_dir / p

    sitemap_path = _out_path(args.output_sitemap, "sitemap.json")
    sessions_path = _out_path(args.output_sessions, "sessions.json")
    report_path = _out_path(args.output_report, "report.html")

    if args.analyze_only:
        if not args.log_path:
            print("--analyze-only の場合は --log-path が必須です。", file=sys.stderr)
            sys.exit(1)
        sm_path = args.sitemap or str(sitemap_path)
        if not Path(sm_path).exists():
            print(f"sitemap が見つかりません: {sm_path}", file=sys.stderr)
            sys.exit(1)
        sitemap = load_sitemap_json(sm_path)
    else:
        if args.crawl_only:
            if not args.base_url:
                print("--crawl-only の場合は --base-url が必須です。", file=sys.stderr)
                sys.exit(1)
            print(f"クロール中: {args.base_url} (最大 {args.max_pages} ページ)")
            sitemap = crawl(args.base_url, max_pages=args.max_pages)
            save_sitemap_json(sitemap, sitemap_path)
            print(f"sitemap を保存しました: {sitemap_path}")
            return

        if not args.base_url or not args.log_path:
            print("通常モードでは --base-url と --log-path が必須です。", file=sys.stderr)
            sys.exit(1)

        print(f"クロール中: {args.base_url} (最大 {args.max_pages} ページ)")
        sitemap = crawl(args.base_url, max_pages=args.max_pages)
        save_sitemap_json(sitemap, sitemap_path)
        print(f"sitemap を保存しました: {sitemap_path}")

    if not args.log_path:
        print("ログ解析をスキップ（--log-path 未指定）")
        return

    exclude_ips_path = args.exclude_ips.strip()
    if not exclude_ips_path and (out_dir / "exclude_ips.csv").exists():
        exclude_ips_path = str(out_dir / "exclude_ips.csv")
    exclude_ips: set[str] = set()
    if exclude_ips_path:
        exclude_ips = load_exclude_ips(exclude_ips_path)
        if exclude_ips:
            print(f"除外 IP を読み込みました: {exclude_ips_path} ({len(exclude_ips)} 件)")

    base_netloc = urlparse(args.base_url or "https://example.com").netloc
    print(f"ログ解析中: {args.log_path}")
    sessions = build_sessions(
        args.log_path,
        session_gap_minutes=args.session_gap_minutes,
        base_netloc=base_netloc,
        exclude_ips=exclude_ips,
    )
    save_sessions_json(sessions, sessions_path)
    print(f"セッションを保存しました: {sessions_path} ({len(sessions)} セッション)")

    if not args.crawl_only:
        # analyze-only のとき sitemap は読み込み済み。なければ空で描画
        if args.analyze_only and not sitemap:
            sitemap = {}
            for s in sessions:
                for step in s.steps:
                    if step.path not in sitemap:
                        sitemap[step.path] = PageInfo(url="", path=step.path, title=step.path)
        print("レポート生成中...")
        render_html(
            sitemap,
            sessions,
            report_path,
            base_url=args.base_url,
            excluded_ips=list(exclude_ips),
            lang=args.lang,
        )
        print(f"レポートを保存しました: {report_path}")
        print(f"ブラウザで {report_path.name} を開くと遷移が確認できます。")


if __name__ == "__main__":
    main()
