# Copyright (c) 2026 sin2503. MIT License.
# SPDX-License-Identifier: MIT

"""diagram_paths_and_log_only_hits のユニットテスト。"""

from log_fooot.crawl import PageInfo
from log_fooot.sessions import Session, Step
from log_fooot.visualize import diagram_paths_and_log_only_hits


def _step(path: str) -> Step:
    return Step(path=path, time=None, status=200, referer="", user_agent="")


def test_crawl_sitemap_excludes_log_only_from_diagram_cards():
    sitemap = {
        "/": PageInfo(url="http://x/", path="/", title="Home", links_out=[]),
        "/about": PageInfo(url="http://x/about", path="/about", title="About", links_out=[]),
    }
    sessions = [
        Session(
            ip="1.1.1.1",
            steps=[_step("/"), _step("/ghost"), _step("/ghost"), _step("/about")],
        )
    ]
    diagram, log_only = diagram_paths_and_log_only_hits(sitemap, sessions, set())
    assert diagram == ["/", "/about"]
    assert log_only == [("/ghost", 2)]


def test_empty_sitemap_falls_back_to_union_no_log_only_section():
    sitemap: dict[str, PageInfo] = {}
    sessions = [Session(ip="1.1.1.1", steps=[_step("/z")])]
    diagram, log_only = diagram_paths_and_log_only_hits(sitemap, sessions, set())
    assert diagram == ["/z"]
    assert log_only == []


def test_excluded_paths_skipped_for_log_only_counts():
    sitemap = {"/": PageInfo(url="http://x/", path="/", title="H", links_out=[])}
    sessions = [Session(ip="1.1.1.1", steps=[_step("/bad"), _step("/bad")])]
    diagram, log_only = diagram_paths_and_log_only_hits(sitemap, sessions, {"/bad"})
    assert diagram == ["/"]
    assert log_only == []
