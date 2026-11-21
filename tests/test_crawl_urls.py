from urllib.parse import urljoin

from log_fooot.crawl import _directory_base_url, _normalize_url, _path_from_url


def test_urljoin_without_trailing_slash_loses_parent():
    # バグ再現: /ft8 をファイル扱いすると howto/ が /howto/ になる
    assert urljoin("https://an-shin.net/ft8", "howto/") == "https://an-shin.net/howto/"
    assert urljoin("https://an-shin.net/ft8/", "howto/") == "https://an-shin.net/ft8/howto/"


def test_directory_base_url_adds_slash_for_extensionless_paths():
    assert _directory_base_url("https://an-shin.net/ft8") == "https://an-shin.net/ft8/"
    assert _directory_base_url("https://an-shin.net/ft8/") == "https://an-shin.net/ft8/"
    assert _directory_base_url("https://an-shin.net/") == "https://an-shin.net/"
    assert _directory_base_url("https://an-shin.net/page.html") == "https://an-shin.net/page.html"


def test_relative_howto_under_ft8():
    base = _directory_base_url("https://an-shin.net/ft8")
    absolute = _normalize_url(base, "howto/")
    assert absolute == "https://an-shin.net/ft8/howto/"
    assert _path_from_url(absolute) == "/ft8/howto"


def test_relative_privacy_under_banddial():
    base = _directory_base_url("https://an-shin.net/banddial/")
    absolute = _normalize_url(base, "privacy/")
    assert absolute == "https://an-shin.net/banddial/privacy/"
    assert _path_from_url(absolute) == "/banddial/privacy"


def test_path_strips_trailing_slash_for_keys():
    assert _path_from_url("https://an-shin.net/ft8/") == "/ft8"
    assert _path_from_url("https://an-shin.net/ft8") == "/ft8"
