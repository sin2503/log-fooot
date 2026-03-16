import pathlib

from log_fooot.exclude_paths import is_excluded_path, load_exclude_paths, save_exclude_paths


def test_is_excluded_path_exact_and_prefix():
    patterns = {"/admin", "/static/logo.png"}

    # 完全一致
    assert is_excluded_path("/admin", patterns)
    assert is_excluded_path("/static/logo.png", patterns)

    # /admin 配下
    assert is_excluded_path("/admin/users", patterns)
    assert is_excluded_path("/admin/settings/security", patterns)

    # 関係ないパス
    assert not is_excluded_path("/administrator", patterns)
    assert not is_excluded_path("/static/logo2.png", patterns)


def test_save_and_load_exclude_paths_csv(tmp_path):
    patterns = {"/admin", "/blog/draft", "/static/logo.png"}
    p = tmp_path / "exclude_paths.csv"

    save_exclude_paths(p, patterns)
    assert p.exists()

    loaded = load_exclude_paths(p)
    # セットとして等しいこと
    assert loaded == patterns


def test_load_exclude_paths_txt(tmp_path):
    txt = tmp_path / "exclude_paths.txt"
    txt.write_text(
        "/admin  # コメント付き\n"
        "/blog/draft\n"
        "# コメント行\n"
        "/static/logo.png\n",
        encoding="utf-8",
    )

    loaded = load_exclude_paths(txt)
    assert loaded == {"/admin", "/blog/draft", "/static/logo.png"}

