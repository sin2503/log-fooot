"""
セッションと sitemap から、カード＋遷移の線で HTML レポートを生成するモジュール。
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

from .crawl import PageInfo
from .sessions import Session


def _path_to_id(path: str) -> str:
    """パスを HTML id に使える文字列に変換する。"""
    s = path or "/"
    s = re.sub(r"[^\w/]", "_", s)
    return "p_" + s.strip("/").replace("/", "_") or "root"


def _collect_edges(sessions: list[Session]) -> dict[tuple[str, str], int]:
    """(from_path, to_path) -> 遷移回数"""
    edges: dict[tuple[str, str], int] = defaultdict(int)
    for session in sessions:
        steps = session.steps
        for i in range(len(steps) - 1):
            a, b = steps[i].path, steps[i + 1].path
            if a != b:
                edges[(a, b)] += 1
    return dict(edges)


def _collect_edges_with_ips(sessions: list[Session]) -> list[tuple[str, str, int, list[str]]]:
    """(from_path, to_path, count, [ip, ...]) のリスト。同一 (a,b) は1要素で IP をまとめる。"""
    edge_ips: dict[tuple[str, str], list[str]] = defaultdict(list)
    for session in sessions:
        steps = session.steps
        for i in range(len(steps) - 1):
            a, b = steps[i].path, steps[i + 1].path
            if a != b and session.ip not in edge_ips[(a, b)]:
                edge_ips[(a, b)].append(session.ip)
    return [(a, b, len(ips), ips) for (a, b), ips in edge_ips.items()]


def _path_to_ips(sessions: list[Session]) -> dict[str, list[str]]:
    """path -> そのページを閲覧した IP のリスト（重複なし順序付き）。"""
    path_ips: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)
    for session in sessions:
        for step in session.steps:
            if session.ip not in seen[step.path]:
                seen[step.path].add(session.ip)
                path_ips[step.path].append(session.ip)
    return dict(path_ips)


def _ip_to_sessions(sessions: list[Session]) -> dict[str, list[list[dict]]]:
    """IP -> その IP のセッション一覧。各セッションは steps: [{path, time}] のリスト。"""
    ip_sessions: dict[str, list[list[dict]]] = defaultdict(list)
    for s in sessions:
        steps_data = []
        for st in s.steps:
            steps_data.append({
                "path": st.path or "/",
                "time": st.time.isoformat() if st.time else None,
            })
        if steps_data:
            ip_sessions[s.ip].append(steps_data)
    return dict(ip_sessions)


def _ua_counts(sessions: list[Session]) -> list[dict]:
    """User-Agent ごとのリクエスト数。 [{"ua": "...", "count": N}, ...] を件数降順で。"""
    counts: dict[str, int] = defaultdict(int)
    for s in sessions:
        for st in s.steps:
            ua = (st.user_agent or "").strip() or "(なし)"
            counts[ua] += 1
    return [{"ua": ua, "count": c} for ua, c in sorted(counts.items(), key=lambda x: -x[1])]


def _time_counts(sessions: list[Session]) -> list[dict]:
    """時刻（1時間単位）ごとのリクエスト数。 [{"hour": "YYYY-MM-DD HH:00", "count": N}, ...] を時刻昇順で。"""
    counts: dict[str, int] = defaultdict(int)
    for s in sessions:
        for st in s.steps:
            if st.time:
                key = st.time.strftime("%Y-%m-%d %H:00")
                counts[key] += 1
    return [{"hour": h, "count": c} for h, c in sorted(counts.items())]


# 表示言語（HTML・JS 内の文言）
LANG = {
    "en": {
        "title": "log-fooot Transition Report",
        "meta_pages": "Pages",
        "meta_sessions": "Sessions",
        "meta_edges": "Transition edges",
        "tab_transition": "Transitions",
        "tab_ua": "UA List",
        "tab_time": "Time chart",
        "sidebar_exclude_title": "Exclude IPs",
        "sidebar_exclude_hint": "IPs excluded from this report. Edit the list, export as CSV, and use --exclude-ips on the next run or save as exclude_ips.csv in the output dir.",
        "sidebar_add_placeholder": "Enter IP",
        "sidebar_add_btn": "Add",
        "sidebar_import_btn": "Import CSV",
        "sidebar_export_btn": "Export CSV",
        "toggle_close": "Close",
        "toggle_collapse_title": "Collapse menu",
        "toggle_expand_title": "Expand menu",
        "ip_panel_title": "Visitor IPs",
        "ip_panel_empty": "Click a card to show visitor IPs for that page.",
        "ip_panel_hint": "Click an IP to highlight that visitor's path.",
        "ip_filter_placeholder": "Filter by IP...",
        "ip_flow_title": "This IP's path",
        "ip_clear_btn": "Clear selection",
        "ua_table_ua": "User-Agent",
        "ua_table_count": "Requests",
        "panel_title_with_count": "Visitor IPs for this page ({count})",
        "session_label": "Session ",
        "time_locale": "en-US",
    },
    "ja": {
        "title": "log-fooot 遷移レポート",
        "meta_pages": "ページ数",
        "meta_sessions": "セッション数",
        "meta_edges": "遷移エッジ数",
        "tab_transition": "遷移図",
        "tab_ua": "UA一覧",
        "tab_time": "時刻グラフ",
        "sidebar_exclude_title": "除外 IP",
        "sidebar_exclude_hint": "レポート作成時に集計から除外した IP です。リストを編集して CSV をエクスポートし、次回は --exclude-ips で指定するか、出力先の exclude_ips.csv に保存して再生成してください。",
        "sidebar_add_placeholder": "IP を入力",
        "sidebar_add_btn": "追加",
        "sidebar_import_btn": "CSV 取り込み",
        "sidebar_export_btn": "CSV ダウンロード",
        "toggle_close": "閉じる",
        "toggle_collapse_title": "メニューを折りたたむ",
        "toggle_expand_title": "メニューを開く",
        "ip_panel_title": "閲覧した IP",
        "ip_panel_empty": "カードをクリックすると、このページを訪問した IP が表示されます。",
        "ip_panel_hint": "IP をクリックするとその閲覧者の辿った線を強調表示します。",
        "ip_filter_placeholder": "IP でフィルタ...",
        "ip_flow_title": "この IP の閲覧の流れ",
        "ip_clear_btn": "選択を解除",
        "ua_table_ua": "User-Agent",
        "ua_table_count": "リクエスト数",
        "panel_title_with_count": "このページを閲覧した IP ({count})",
        "session_label": "セッション ",
        "time_locale": "ja-JP",
    },
}


def _layout_cards(paths: list[str], card_width: int = 200, card_height: int = 100, gap: int = 24) -> dict[str, tuple[float, float]]:
    """パス一覧をグリッドに並べ、path -> (center_x, center_y) を返す。"""
    n = len(paths)
    if n == 0:
        return {}
    cols = max(1, math.ceil(math.sqrt(n)))
    pos = {}
    for i, path in enumerate(paths):
        row, col = divmod(i, cols)
        x = col * (card_width + gap) + card_width / 2
        y = row * (card_height + gap) + card_height / 2
        pos[path] = (x, y)
    return pos


def render_html(
    sitemap: dict[str, PageInfo],
    sessions: list[Session],
    output_path: str | Path,
    base_url: str = "",
    title: str = "",
    excluded_ips: list[str] | None = None,
    lang: str = "en",
) -> None:
    """
    カード（ページ）と遷移の線を描いた HTML を出力する。
    excluded_ips: レポート作成時に集計から除外した IP のリスト（左サイドバーに表示）。
    lang: 表示言語 "en" または "ja"（既定: "en"）。
    """
    lang = "ja" if lang == "ja" else "en"
    t = LANG[lang]
    if not title:
        title = t["title"]

    all_paths = list(sitemap.keys())
    seen_paths = set(all_paths)
    for s in sessions:
        for step in s.steps:
            if step.path not in seen_paths:
                all_paths.append(step.path)
                seen_paths.add(step.path)

    if not all_paths:
        all_paths = ["/"]

    edges_with_ips = _collect_edges_with_ips(sessions)
    path_to_ips = _path_to_ips(sessions)
    positions = _layout_cards(all_paths)
    card_width, card_height, gap = 200, 100, 24

    path_to_title = {p: (sitemap[p].title if p in sitemap else p) for p in all_paths}

    # SVG の描画領域
    cols = max(1, math.ceil(math.sqrt(len(all_paths))))
    rows = math.ceil(len(all_paths) / cols)
    svg_width = cols * (card_width + gap) + gap
    svg_height = rows * (card_height + gap) + gap

    lines_svg = []
    for (a, b, count, ips) in sorted(edges_with_ips, key=lambda x: -x[2]):
        if a not in positions or b not in positions:
            continue
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        stroke = min(4, 1 + count / 3)
        ips_json = json.dumps(ips, ensure_ascii=False)
        from_esc = (a or "/").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        to_esc = (b or "/").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        lines_svg.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="rgba(100,149,237,0.6)" stroke-width="{stroke:.1f}" class="transition-line" '
            f'data-count="{count}" data-from="{from_esc}" data-to="{to_esc}" data-ips=\'{ips_json}\'/>'
        )

    cards_html = []
    for path in all_paths:
        pid = _path_to_id(path)
        x, y = positions[path]
        cx, cy = x - card_width / 2, y - card_height / 2
        tit = path_to_title.get(path, path)
        tit_esc = tit.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        path_esc = (path or "/").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        cards_html.append(
            f'<div id="{pid}" class="card" style="left:{cx:.0f}px;top:{cy:.0f}px" '
            f'data-path="{path_esc}">'
            f'<div class="card-path">{path_esc}</div>'
            f'<div class="card-title" title="{tit_esc}">{tit_esc[:40]}{"…" if len(tit) > 40 else ""}</div>'
            f"</div>"
        )

    path_to_ips_json = json.dumps(path_to_ips, ensure_ascii=False)
    ip_to_sessions = _ip_to_sessions(sessions)
    ip_to_sessions_json = json.dumps(ip_to_sessions, ensure_ascii=False)
    excluded_ips = excluded_ips or []
    excluded_ips_json = json.dumps(excluded_ips, ensure_ascii=False)
    ua_counts = _ua_counts(sessions)
    ua_counts_json = json.dumps(ua_counts, ensure_ascii=False)
    time_counts = _time_counts(sessions)
    time_counts_json = json.dumps(time_counts, ensure_ascii=False)
    time_max = max((x["count"] for x in time_counts), default=1)
    lang_strings_json = json.dumps(
        {
            "panelTitleWithCount": t["panel_title_with_count"],
            "sessionLabel": t["session_label"],
            "toggleClose": t["toggle_close"],
            "toggleCollapseTitle": t["toggle_collapse_title"],
            "toggleExpandTitle": t["toggle_expand_title"],
            "timeLocale": t["time_locale"],
        },
        ensure_ascii=False,
    )

    meta_pages = t["meta_pages"]
    meta_sessions = t["meta_sessions"]
    meta_edges = t["meta_edges"]
    tab_transition = t["tab_transition"]
    tab_ua = t["tab_ua"]
    tab_time = t["tab_time"]
    sidebar_exclude_title = t["sidebar_exclude_title"]
    sidebar_exclude_hint = t["sidebar_exclude_hint"]
    sidebar_add_placeholder = t["sidebar_add_placeholder"]
    sidebar_add_btn = t["sidebar_add_btn"]
    sidebar_import_btn = t["sidebar_import_btn"]
    sidebar_export_btn = t["sidebar_export_btn"]
    toggle_close = t["toggle_close"]
    toggle_collapse_title = t["toggle_collapse_title"]
    ip_panel_title = t["ip_panel_title"]
    ip_panel_hint = t["ip_panel_hint"]
    ip_filter_placeholder = t["ip_filter_placeholder"]
    ip_flow_title = t["ip_flow_title"]
    ip_clear_btn = t["ip_clear_btn"]
    ip_panel_empty = t["ip_panel_empty"]
    ua_table_ua = t["ua_table_ua"]
    ua_table_count = t["ua_table_count"]

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, "Segoe UI", sans-serif; margin: 0; padding: 0; background: #1a1b26; color: #c0caf5; }}
  .app {{ display: flex; height: 100vh; overflow: hidden; }}
  .sidebar {{
    flex-shrink: 0;
    min-width: 180px;
    max-width: 480px;
    background: #24283b;
    border-right: 1px solid #414868;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: width 0.2s ease, min-width 0.2s ease;
  }}
  .sidebar.collapsed {{
    min-width: 0;
    width: 32px !important;
    max-width: 32px;
  }}
  .sidebar.collapsed .sidebar-inner {{ display: none; }}
  .sidebar-toggle {{
    flex-shrink: 0;
    padding: 8px 10px;
    font-size: 0.75rem;
    background: #1a1b26;
    border: none;
    border-bottom: 1px solid #414868;
    color: #7aa2f7;
    cursor: pointer;
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
  }}
  .sidebar-toggle:hover {{ background: #414868; color: #c0caf5; }}
  .sidebar.collapsed .sidebar-toggle {{
    border-bottom: none;
    height: 72px;
    padding: 8px 0;
    font-size: 1rem;
  }}
  .sidebar-resizer {{
    flex-shrink: 0;
    width: 6px;
    background: transparent;
    cursor: col-resize;
    transition: opacity 0.2s;
  }}
  .sidebar-resizer:hover {{ background: #414868; }}
  .sidebar.collapsed + .sidebar-resizer {{ width: 0; min-width: 0; pointer-events: none; opacity: 0; }}
  .sidebar-inner {{ padding: 12px; flex: 1; min-height: 0; overflow: auto; }}
  .sidebar h3 {{ font-size: 0.875rem; margin: 0 0 10px 0; color: #7aa2f7; }}
  .exclude-hint {{ font-size: 0.7rem; color: #565f89; margin-bottom: 8px; line-height: 1.4; }}
  .exclude-list {{ max-height: 120px; overflow-y: auto; margin-bottom: 8px; font-size: 0.75rem; font-family: ui-monospace, monospace; }}
  .exclude-list li {{ padding: 2px 0; color: #a9b1d6; display: flex; align-items: center; justify-content: space-between; gap: 6px; }}
  .exclude-list li .exclude-rm {{ padding: 0 4px; cursor: pointer; color: #565f89; }}
  .exclude-list li .exclude-rm:hover {{ color: #f7768e; }}
  .exclude-add {{ display: flex; gap: 6px; margin-bottom: 8px; }}
  .exclude-add input {{ flex: 1; padding: 4px 8px; font-size: 0.8rem; background: #1a1b26; border: 1px solid #414868; border-radius: 4px; color: #c0caf5; }}
  .exclude-add button {{ padding: 4px 10px; font-size: 0.75rem; background: #414868; color: #a9b1d6; border: none; border-radius: 4px; cursor: pointer; }}
  .exclude-add button:hover {{ background: #565f89; color: #c0caf5; }}
  .exclude-btns {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .exclude-btns button {{ padding: 4px 10px; font-size: 0.75rem; background: #414868; color: #a9b1d6; border: none; border-radius: 4px; cursor: pointer; }}
  .exclude-btns button:hover {{ background: #565f89; color: #c0caf5; }}
  .exclude-btns input[type=file] {{ display: none; }}
  .main {{ flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }}
  .main-inner {{ flex: 1; display: flex; min-height: 0; overflow: hidden; }}
  .main-left {{ flex: 1; min-width: 0; overflow: auto; padding: 16px; }}
  .main-right {{ width: 320px; flex-shrink: 0; border-left: 1px solid #414868; background: #24283b; overflow: auto; padding: 12px; }}
  .main-left h1 {{ font-size: 1.25rem; margin-bottom: 8px; }}
  .meta {{ font-size: 0.875rem; color: #565f89; margin-bottom: 12px; }}
  .tabs {{ display: flex; gap: 4px; margin-bottom: 16px; }}
  .tab-btn {{ padding: 8px 16px; font-size: 0.875rem; background: #414868; color: #a9b1d6; border: none; border-radius: 6px; cursor: pointer; }}
  .tab-btn:hover {{ background: #565f89; color: #c0caf5; }}
  .tab-btn.active {{ background: #7aa2f7; color: #1a1b26; }}
  .tab-pane {{ display: none; min-height: 0; }}
  .tab-pane.active {{ display: block; }}
  .layout {{ display: flex; justify-content: flex-start; align-items: flex-start; }}
  .ua-table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  .ua-table th, .ua-table td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #414868; }}
  .ua-table th {{ color: #7aa2f7; }}
  .ua-table td {{ color: #a9b1d6; }}
  .ua-table tr:hover td {{ background: #2a2b36; }}
  .time-chart {{ display: flex; flex-direction: column; gap: 6px; max-width: 800px; }}
  .time-chart-row {{ display: flex; align-items: center; gap: 12px; }}
  .time-chart-label {{ width: 140px; font-size: 0.75rem; font-family: ui-monospace, monospace; color: #565f89; flex-shrink: 0; }}
  .time-chart-bar-wrap {{ flex: 1; height: 20px; background: #24283b; border-radius: 4px; overflow: hidden; }}
  .time-chart-bar {{ height: 100%; background: #7aa2f7; border-radius: 4px; min-width: 2px; }}
  .time-chart-count {{ width: 50px; font-size: 0.75rem; color: #a9b1d6; text-align: right; }}
  .canvas {{ position: relative; width: {svg_width:.0f}px; height: {svg_height:.0f}px; flex-shrink: 0; }}
  .transition-line {{ stroke-linecap: round; transition: stroke 0.2s, stroke-width 0.2s, opacity 0.2s; }}
  .transition-line:hover {{ stroke: #7aa2f7; stroke-width: 5; }}
  .transition-line.dimmed {{ opacity: 0.15; }}
  .transition-line.highlight {{ stroke: #bb9af7; stroke-width: 4; opacity: 1; }}
  .card {{
    position: absolute;
    width: {card_width}px;
    height: {card_height}px;
    background: #24283b;
    border: 1px solid #414868;
    border-radius: 8px;
    padding: 10px 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    cursor: pointer;
  }}
  .card:hover {{ border-color: #7aa2f7; }}
  .card.card-selected {{ border-color: #bb9af7; box-shadow: 0 0 0 2px #bb9af7; }}
  .card-path {{ font-size: 0.7rem; color: #7aa2f7; word-break: break-all; margin-bottom: 4px; }}
  .card-title {{ font-size: 0.85rem; color: #a9b1d6; line-height: 1.3; }}
  svg {{ position: absolute; left: 0; top: 0; width: 100%; height: 100%; pointer-events: none; }}
  svg line {{ pointer-events: stroke; }}
  .ip-panel {{ height: 100%; display: flex; flex-direction: column; min-height: 0; }}
  .ip-panel-empty {{ font-size: 0.8rem; color: #565f89; line-height: 1.5; padding: 8px 0; }}
  .ip-panel-content {{ display: none; flex: 1; min-height: 0; flex-direction: column; }}
  .ip-panel-content.visible {{ display: flex; }}
  .ip-panel h3 {{ font-size: 0.875rem; margin: 0 0 8px 0; color: #7aa2f7; flex-shrink: 0; }}
  .ip-panel .hint {{ font-size: 0.75rem; color: #565f89; margin-bottom: 8px; flex-shrink: 0; }}
  .ip-filter-wrap {{ margin-bottom: 8px; }}
  .ip-filter {{
    width: 100%;
    padding: 6px 10px;
    font-size: 0.8rem;
    font-family: ui-monospace, monospace;
    background: #1a1b26;
    border: 1px solid #414868;
    border-radius: 6px;
    color: #c0caf5;
  }}
  .ip-filter::placeholder {{ color: #565f89; }}
  .ip-filter:focus {{ outline: none; border-color: #7aa2f7; }}
  .ip-list {{ display: flex; flex-direction: column; gap: 4px; max-height: 200px; overflow-y: auto; }}
  .ip-item {{
    display: block;
    padding: 6px 10px;
    background: #1a1b26;
    border-radius: 6px;
    font-size: 0.8rem; font-family: ui-monospace, monospace;
    color: #a9b1d6;
    cursor: pointer;
    border: 1px solid transparent;
  }}
  .ip-item:hover {{ border-color: #7aa2f7; color: #c0caf5; }}
  .ip-item.ip-selected {{ border-color: #bb9af7; color: #bb9af7; background: #2a2b36; }}
  .ip-clear-btn {{
    margin-top: 10px;
    padding: 6px 12px;
    font-size: 0.8rem;
    background: #414868;
    color: #a9b1d6;
    border: 1px solid #565f89;
    border-radius: 6px;
    cursor: pointer;
    width: 100%;
  }}
  .ip-clear-btn:hover {{ background: #565f89; color: #c0caf5; }}
  .ip-flow {{ margin-top: 12px; padding-top: 12px; border-top: 1px solid #414868; }}
  .ip-flow h4 {{ font-size: 0.8rem; margin: 0 0 8px 0; color: #bb9af7; }}
  .ip-flow-session {{ margin-bottom: 12px; }}
  .ip-flow-session:last-child {{ margin-bottom: 0; }}
  .ip-flow-steps {{ display: flex; flex-wrap: wrap; align-items: center; gap: 4px; font-size: 0.75rem; font-family: ui-monospace, monospace; }}
  .ip-flow-step {{ padding: 2px 6px; background: #1a1b26; border-radius: 4px; color: #7aa2f7; }}
  .ip-flow-step time {{ color: #565f89; font-size: 0.7rem; margin-left: 2px; }}
  .ip-flow-arrow {{ color: #565f89; font-size: 0.7rem; }}
</style>
</head>
<body>
<div class="app">
<div class="sidebar" id="sidebar">
  <button type="button" class="sidebar-toggle" id="sidebar-toggle" title="{toggle_collapse_title}">◀ {toggle_close}</button>
  <div class="sidebar-inner">
    <h3>{sidebar_exclude_title}</h3>
    <p class="exclude-hint">{sidebar_exclude_hint}</p>
    <ul class="exclude-list" id="exclude-list"></ul>
    <div class="exclude-add">
      <input type="text" id="exclude-ip-input" placeholder="{sidebar_add_placeholder}" />
      <button type="button" id="exclude-add-btn">{sidebar_add_btn}</button>
    </div>
    <div class="exclude-btns">
      <button type="button" id="exclude-import-btn">{sidebar_import_btn}</button>
      <input type="file" id="exclude-file-input" accept=".csv,.txt" />
      <button type="button" id="exclude-export-btn">{sidebar_export_btn}</button>
    </div>
  </div>
</div>
<div class="sidebar-resizer" id="sidebar-resizer"></div>
<div class="main">
<div class="main-inner">
<div class="main-left">
<h1>{title}</h1>
<p class="meta">{meta_pages}: {len(all_paths)} / {meta_sessions}: {len(sessions)} / {meta_edges}: {len(edges_with_ips)}</p>
<div class="tabs">
  <button type="button" class="tab-btn active" data-tab="transition">{tab_transition}</button>
  <button type="button" class="tab-btn" data-tab="ua">{tab_ua}</button>
  <button type="button" class="tab-btn" data-tab="time">{tab_time}</button>
</div>
<div id="tab-transition" class="tab-pane active">
<div class="layout">
<div class="canvas">
<svg width="{svg_width:.0f}" height="{svg_height:.0f}" xmlns="http://www.w3.org/2000/svg">
  {"".join(lines_svg)}
</svg>
{"".join(cards_html)}
</div>
</div>
</div>
<div id="tab-ua" class="tab-pane">
  <table class="ua-table" id="ua-table">
    <thead><tr><th>{ua_table_ua}</th><th>{ua_table_count}</th></tr></thead>
    <tbody id="ua-tbody"></tbody>
  </table>
</div>
<div id="tab-time" class="tab-pane">
  <div class="time-chart" id="time-chart"></div>
</div>
</div>
<div class="main-right">
<div class="ip-panel" id="ip-panel">
  <p class="ip-panel-empty" id="ip-panel-empty">{ip_panel_empty}</p>
  <div class="ip-panel-content" id="ip-panel-content">
    <h3 id="ip-panel-title">{ip_panel_title}</h3>
    <p class="hint" id="ip-panel-hint">{ip_panel_hint}</p>
    <div class="ip-filter-wrap">
      <input type="text" class="ip-filter" id="ip-filter" placeholder="{ip_filter_placeholder}" autocomplete="off"/>
    </div>
    <div class="ip-list" id="ip-list"></div>
    <div class="ip-flow" id="ip-flow" style="display:none">
      <h4>{ip_flow_title}</h4>
      <div id="ip-flow-body"></div>
    </div>
    <button type="button" class="ip-clear-btn" id="ip-clear-btn" style="display:none">{ip_clear_btn}</button>
  </div>
</div>
</div>
</div>
</div>
</div>
<script>
(function() {{
  var pathToIps = {path_to_ips_json};
  var ipToSessions = {ip_to_sessions_json};
  var excludedIps = {excluded_ips_json};
  var uaCounts = {ua_counts_json};
  var timeCounts = {time_counts_json};
  var timeMax = {time_max};
  var langStrings = {lang_strings_json};
  var lines = document.querySelectorAll('.transition-line');
  var cards = document.querySelectorAll('.card');
  var panel = document.getElementById('ip-panel');
  var ipPanelEmpty = document.getElementById('ip-panel-empty');
  var ipPanelContent = document.getElementById('ip-panel-content');
  var panelTitle = document.getElementById('ip-panel-title');
  var ipListEl = document.getElementById('ip-list');
  var ipFilterEl = document.getElementById('ip-filter');
  var ipFlowEl = document.getElementById('ip-flow');
  var ipFlowBody = document.getElementById('ip-flow-body');
  var clearBtn = document.getElementById('ip-clear-btn');
  var selectedIp = null;
  var currentIps = [];

  var SIDEBAR_STORAGE_KEY = 'log-fooot-sidebar-width';
  var SIDEBAR_COLLAPSED_KEY = 'log-fooot-sidebar-collapsed';
  var sidebar = document.getElementById('sidebar');
  var sidebarToggle = document.getElementById('sidebar-toggle');
  var resizer = document.getElementById('sidebar-resizer');
  var excludeListEl = document.getElementById('exclude-list');
  var excludeInput = document.getElementById('exclude-ip-input');
  var excludeAddBtn = document.getElementById('exclude-add-btn');
  var excludeImportBtn = document.getElementById('exclude-import-btn');
  var excludeFileInput = document.getElementById('exclude-file-input');
  var excludeExportBtn = document.getElementById('exclude-export-btn');

  var excludeSet = new Set(excludedIps);

  function renderExcludeList() {{
    if (!excludeListEl) return;
    excludeListEl.innerHTML = '';
    Array.from(excludeSet).sort().forEach(function(ip) {{
      var li = document.createElement('li');
      li.textContent = ip;
      var rm = document.createElement('span');
      rm.className = 'exclude-rm';
      rm.textContent = '×';
      rm.addEventListener('click', function() {{ excludeSet.delete(ip); renderExcludeList(); }});
      li.appendChild(rm);
      excludeListEl.appendChild(li);
    }});
  }}

  function addExcludeIp(ip) {{
    ip = (ip || '').trim();
    if (ip) {{ excludeSet.add(ip); renderExcludeList(); }}
  }}

  if (excludeAddBtn && excludeInput) {{
    excludeAddBtn.addEventListener('click', function() {{ addExcludeIp(excludeInput.value); excludeInput.value = ''; }});
    excludeInput.addEventListener('keydown', function(e) {{ if (e.key === 'Enter') {{ addExcludeIp(excludeInput.value); excludeInput.value = ''; }} }});
  }}
  if (excludeImportBtn && excludeFileInput) {{
    excludeImportBtn.addEventListener('click', function() {{ excludeFileInput.click(); }});
    excludeFileInput.addEventListener('change', function() {{
      var f = this.files && this.files[0];
      if (!f) return;
      var r = new FileReader();
      r.onload = function() {{
        var text = r.result;
        var lines = text.split(/\\r?\\n/);
        lines.forEach(function(line, i) {{
          var ip = line.split(',')[0].trim();
          if (i === 0 && ip.toLowerCase() === 'ip') return;
          if (ip && /^[\\d.]+$/.test(ip)) excludeSet.add(ip);
        }});
        renderExcludeList();
      }};
      r.readAsText(f, 'utf-8');
      this.value = '';
    }});
  }}
  if (excludeExportBtn) {{
    excludeExportBtn.addEventListener('click', function() {{
      var csv = 'ip\\n' + Array.from(excludeSet).sort().map(function(ip) {{ return ip; }}).join('\\n');
      var a = document.createElement('a');
      a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
      a.download = 'exclude_ips.csv';
      a.click();
    }});
  }}
  renderExcludeList();

  (function initTabs() {{
    var tabBtns = document.querySelectorAll('.tab-btn');
    var tabPanes = document.querySelectorAll('.tab-pane');
    tabBtns.forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        var tab = btn.getAttribute('data-tab');
        tabBtns.forEach(function(b) {{ b.classList.remove('active'); }});
        tabPanes.forEach(function(p) {{ p.classList.remove('active'); }});
        btn.classList.add('active');
        var pane = document.getElementById('tab-' + tab);
        if (pane) pane.classList.add('active');
      }});
    }});
  }})();

  (function initUaList() {{
    var tbody = document.getElementById('ua-tbody');
    if (!tbody) return;
    uaCounts.forEach(function(row) {{
      var tr = document.createElement('tr');
      var ua = document.createElement('td');
      ua.textContent = row.ua;
      ua.style.wordBreak = 'break-all';
      var count = document.createElement('td');
      count.textContent = row.count.toLocaleString();
      tr.appendChild(ua);
      tr.appendChild(count);
      tbody.appendChild(tr);
    }});
  }})();

  (function initTimeChart() {{
    var chart = document.getElementById('time-chart');
    if (!chart || !timeCounts.length) return;
    timeCounts.forEach(function(row) {{
      var wrap = document.createElement('div');
      wrap.className = 'time-chart-row';
      var label = document.createElement('span');
      label.className = 'time-chart-label';
      label.textContent = row.hour;
      var barWrap = document.createElement('div');
      barWrap.className = 'time-chart-bar-wrap';
      var bar = document.createElement('div');
      bar.className = 'time-chart-bar';
      bar.style.width = (timeMax > 0 ? (row.count / timeMax * 100) : 0) + '%';
      var count = document.createElement('span');
      count.className = 'time-chart-count';
      count.textContent = row.count.toLocaleString();
      barWrap.appendChild(bar);
      wrap.appendChild(label);
      wrap.appendChild(barWrap);
      wrap.appendChild(count);
      chart.appendChild(wrap);
    }});
  }})();

  var sidebarWidth = parseInt(localStorage.getItem(SIDEBAR_STORAGE_KEY), 10) || 260;
  var sidebarCollapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1';
  if (sidebar && !isNaN(sidebarWidth) && !sidebarCollapsed) {{ sidebar.style.width = sidebarWidth + 'px'; }}
  if (sidebar && sidebarCollapsed) {{ sidebar.classList.add('collapsed'); }}
  if (sidebarToggle) {{
    function updateToggleText() {{
      var collapsed = sidebar && sidebar.classList.contains('collapsed');
      sidebarToggle.textContent = collapsed ? '▶' : '◀ ' + (langStrings.toggleClose || 'Close');
      sidebarToggle.title = collapsed ? (langStrings.toggleExpandTitle || 'Expand menu') : (langStrings.toggleCollapseTitle || 'Collapse menu');
    }}
    updateToggleText();
    sidebarToggle.addEventListener('click', function() {{
      if (!sidebar) return;
      sidebar.classList.toggle('collapsed');
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebar.classList.contains('collapsed') ? '1' : '0');
      if (!sidebar.classList.contains('collapsed')) {{
        var w = parseInt(localStorage.getItem(SIDEBAR_STORAGE_KEY), 10) || 260;
        sidebar.style.width = w + 'px';
      }}
      updateToggleText();
    }});
  }}
  if (resizer && sidebar) {{
    var startX, startW;
    resizer.addEventListener('mousedown', function(e) {{
      e.preventDefault();
      startX = e.clientX;
      startW = sidebar.offsetWidth;
      document.addEventListener('mousemove', onResize);
      document.addEventListener('mouseup', function onUp() {{ document.removeEventListener('mousemove', onResize); document.removeEventListener('mouseup', onUp); }});
    }});
    function onResize(e) {{
      var dx = e.clientX - startX;
      var w = Math.max(180, Math.min(480, startW + dx));
      sidebar.style.width = w + 'px';
      localStorage.setItem(SIDEBAR_STORAGE_KEY, String(w));
    }}
  }}

  function getLineIps(line) {{
    var raw = line.getAttribute('data-ips');
    if (!raw) return [];
    try {{ return JSON.parse(raw); }} catch (e) {{ return []; }}
  }}

  function formatTime(iso) {{
    if (!iso) return '';
    try {{
      var d = new Date(iso);
      var locale = (langStrings && langStrings.timeLocale) || 'en-US';
      return d.toLocaleTimeString(locale, {{ hour: '2-digit', minute: '2-digit', second: '2-digit' }});
    }} catch (e) {{ return iso; }}
  }}

  function renderIpFlow(ip) {{
    if (!ipFlowEl || !ipFlowBody) return;
    var sessions = ipToSessions[ip];
    if (!sessions || sessions.length === 0) {{
      ipFlowEl.style.display = 'none';
      return;
    }}
    ipFlowEl.style.display = 'block';
    ipFlowBody.innerHTML = '';
    sessions.forEach(function(steps, idx) {{
      var wrap = document.createElement('div');
      wrap.className = 'ip-flow-session';
      if (sessions.length > 1) {{
        var cap = document.createElement('div');
        cap.style.cssText = 'font-size:0.7rem;color:#565f89;margin-bottom:4px;';
        cap.textContent = (langStrings.sessionLabel || 'Session ') + (idx + 1);
        wrap.appendChild(cap);
      }}
      var stepsEl = document.createElement('div');
      stepsEl.className = 'ip-flow-steps';
      steps.forEach(function(step, i) {{
        if (i > 0) {{
          var arrow = document.createElement('span');
          arrow.className = 'ip-flow-arrow';
          arrow.textContent = ' → ';
          stepsEl.appendChild(arrow);
        }}
        var span = document.createElement('span');
        span.className = 'ip-flow-step';
        span.textContent = step.path || '/';
        if (step.time) {{
          var timeEl = document.createElement('time');
          timeEl.textContent = ' ' + formatTime(step.time);
          span.appendChild(timeEl);
        }}
        stepsEl.appendChild(span);
      }});
      wrap.appendChild(stepsEl);
      ipFlowBody.appendChild(wrap);
    }});
  }}

  function selectIp(ip) {{
    selectedIp = ip;
    if (clearBtn) clearBtn.style.display = 'block';
    renderIpFlow(ip);
    document.querySelectorAll('.ip-item').forEach(function(el) {{
      el.classList.toggle('ip-selected', el.textContent.trim() === ip);
    }});
    lines.forEach(function(line) {{
      var ips = getLineIps(line);
      var on = ips.indexOf(ip) !== -1;
      line.classList.toggle('highlight', on);
      line.classList.toggle('dimmed', !on && selectedIp !== null);
    }});
  }}

  function showIpPanelEmpty() {{
    if (ipPanelEmpty) ipPanelEmpty.style.display = '';
    if (ipPanelContent) ipPanelContent.classList.remove('visible');
  }}
  function showIpPanelContent() {{
    if (ipPanelEmpty) ipPanelEmpty.style.display = 'none';
    if (ipPanelContent) ipPanelContent.classList.add('visible');
  }}

  function clearIpSelection() {{
    selectedIp = null;
    if (clearBtn) clearBtn.style.display = 'none';
    if (ipFlowEl) ipFlowEl.style.display = 'none';
    if (ipFlowBody) ipFlowBody.innerHTML = '';
    document.querySelectorAll('.ip-item').forEach(function(el) {{ el.classList.remove('ip-selected'); }});
    lines.forEach(function(line) {{
      line.classList.remove('highlight');
      line.classList.remove('dimmed');
    }});
  }}

  if (clearBtn) clearBtn.addEventListener('click', function(e) {{ e.stopPropagation(); clearIpSelection(); }});

  function renderIpList(ips, filterStr) {{
    var q = (filterStr || '').trim().toLowerCase();
    var filtered = q ? ips.filter(function(ip) {{ return ip.toLowerCase().indexOf(q) !== -1; }}) : ips;
    ipListEl.innerHTML = '';
    filtered.forEach(function(ip) {{
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ip-item' + (ip === selectedIp ? ' ip-selected' : '');
      btn.textContent = ip;
      btn.setAttribute('data-ip', ip);
      btn.addEventListener('click', function(e) {{
        e.stopPropagation();
        if (ip === selectedIp) {{ clearIpSelection(); return; }}
        selectIp(ip);
      }});
      ipListEl.appendChild(btn);
    }});
  }}

  if (ipFilterEl) {{
    ipFilterEl.addEventListener('input', function() {{ renderIpList(currentIps, ipFilterEl.value); }});
    ipFilterEl.addEventListener('keydown', function(e) {{ e.stopPropagation(); }});
  }}

  cards.forEach(function(card) {{
    card.addEventListener('click', function() {{
      var path = card.getAttribute('data-path') || '/';
      var ips = pathToIps[path] || [];
      card.classList.add('card-selected');
      cards.forEach(function(c) {{ if (c !== card) c.classList.remove('card-selected'); }});
      if (ips.length === 0) {{
        showIpPanelEmpty();
        clearIpSelection();
        return;
      }}
      showIpPanelContent();
      currentIps = ips;
      if (ipFilterEl) ipFilterEl.value = '';
      panelTitle.textContent = (langStrings.panelTitleWithCount || 'Visitor IPs for this page ({count})').replace('{{count}}', ips.length);
      renderIpList(ips, '');
      if (selectedIp && ips.indexOf(selectedIp) !== -1) {{
        selectIp(selectedIp);
      }} else if (selectedIp) {{
        lines.forEach(function(line) {{
          line.classList.remove('highlight');
          line.classList.remove('dimmed');
        }});
      }}
    }});
  }});

  document.addEventListener('click', function(e) {{
    if (panel.contains(e.target) || e.target.closest('.card')) return;
    showIpPanelEmpty();
    cards.forEach(function(c) {{ c.classList.remove('card-selected'); }});
    clearIpSelection();
  }});
}})();
</script>
</body>
</html>
"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")


def save_sitemap_json(sitemap: dict[str, PageInfo], output_path: str | Path) -> None:
    """sitemap を JSON で保存する。"""
    data = {
        path: {
            "url": info.url,
            "path": info.path,
            "title": info.title,
            "links_out": info.links_out,
        }
        for path, info in sitemap.items()
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_sitemap_json(path: str | Path) -> dict[str, PageInfo]:
    """JSON から sitemap を読み込む。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        p: PageInfo(
            url=v["url"],
            path=v["path"],
            title=v["title"],
            links_out=v.get("links_out", []),
        )
        for p, v in data.items()
    }


def save_sessions_json(sessions: list[Session], output_path: str | Path) -> None:
    """セッション一覧を JSON で保存する。"""
    def step_to_dict(s):
        return {
            "path": s.path,
            "time": s.time.isoformat() if s.time else None,
            "status": s.status,
            "referer": s.referer,
            "user_agent": getattr(s, "user_agent", "") or "",
        }

    data = [{"ip": s.ip, "steps": [step_to_dict(st) for st in s.steps]} for s in sessions]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
