import pytest

from app.ingest.arxiv import ArxivError, _parse_feed, parse_arxiv_id

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <published>2017-06-12T17:57:34Z</published>
    <summary>The dominant sequence transduction models are based on recurrent networks.</summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <link title="pdf" href="http://arxiv.org/pdf/1706.03762v7"/>
  </entry>
</feed>"""

ERROR_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Error</title><summary>incorrect id format</summary></entry>
</feed>"""


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1706.03762", "1706.03762"),
        ("arXiv:1706.03762v5", "1706.03762"),
        ("https://arxiv.org/abs/1706.03762", "1706.03762"),
        ("https://arxiv.org/pdf/1706.03762v5.pdf", "1706.03762"),
        ("  2401.00001  ", "2401.00001"),
        ("https://arxiv.org/abs/math.GT/0309136", "math.GT/0309136"),
        ("not a paper at all", None),
        ("", None),
    ],
)
def test_parse_arxiv_id(raw, expected):
    assert parse_arxiv_id(raw) == expected


def test_parse_feed_reads_metadata():
    paper = _parse_feed(FEED, "1706.03762")
    assert paper.meta.title == "Attention Is All You Need"
    assert paper.meta.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert paper.meta.year == 2017
    assert paper.meta.arxiv_id == "1706.03762"
    assert paper.meta.source_url == "https://arxiv.org/abs/1706.03762"
    assert "recurrent networks" in paper.meta.abstract
    assert paper.pdf_url.endswith("1706.03762v7")


def test_parse_feed_rejects_an_error_entry():
    with pytest.raises(ArxivError, match="no record"):
        _parse_feed(ERROR_FEED, "9999.99999")


def test_parse_feed_rejects_an_empty_feed():
    with pytest.raises(ArxivError, match="no record"):
        _parse_feed('<feed xmlns="http://www.w3.org/2005/Atom"></feed>', "1234.5678")
