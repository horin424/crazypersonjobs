from scrapers.base import absolute_url, extract_project_id


def test_lancers_project_id():
    assert extract_project_id("https://www.lancers.jp/work/detail/5610891", "lancers") == "5610891"


def test_crowdworks_project_id():
    assert extract_project_id("https://crowdworks.jp/public/jobs/13497398", "crowdworks") == "13497398"


def test_absolute_url_conversion():
    assert absolute_url("https://www.lancers.jp", "/work/detail/5610891") == "https://www.lancers.jp/work/detail/5610891"


def test_unrelated_url_is_rejected():
    assert extract_project_id("https://example.com/no/project", "lancers") is None

