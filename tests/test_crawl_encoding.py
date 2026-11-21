from types import SimpleNamespace

from log_fooot.crawl import _html_text_from_response


def test_html_text_prefers_utf8_over_latin1_charset():
    # 「を」の UTF-8 バイト列。Content-Type が latin-1 でも正しく読む。
    body = "IC-705 を iPhone".encode("utf-8")
    resp = SimpleNamespace(
        content=body,
        charset_encoding="iso-8859-1",
        encoding="iso-8859-1",
    )
    text = _html_text_from_response(resp)
    assert "を" in text
    assert "ã" not in text


def test_html_text_falls_back_when_not_utf8():
    # latin-1 専用のバイト（0xE9）は UTF-8 として無効なのでフォールバックする
    body = b"caf\xe9"
    resp = SimpleNamespace(
        content=body,
        charset_encoding="iso-8859-1",
        encoding="iso-8859-1",
    )
    assert _html_text_from_response(resp) == "café"


def test_html_text_strips_utf8_bom():
    body = b"\xef\xbb\xbf<title>hello</title>"
    resp = SimpleNamespace(content=body, charset_encoding=None, encoding=None)
    assert _html_text_from_response(resp).startswith("<title>")
