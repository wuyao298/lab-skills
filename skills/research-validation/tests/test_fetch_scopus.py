import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fetch_scopus


def test_load_key_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SCOPUS_API_KEY=abc123\n", encoding="utf-8")
    assert fetch_scopus.load_api_key(str(env)) == "abc123"


def test_load_key_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("SCOPUS_API_KEY", "env-key")
    assert fetch_scopus.load_api_key(None) == "env-key"


def test_total_results_and_entries():
    data = json.loads(
        (os.path.join(os.path.dirname(__file__), "fixtures", "mini_scopus_raw.json")
         if False else json.dumps({
             "search-results": {"opensearch:totalResults": "42", "entry": [{"eid": "x"}]}
         })))
    assert fetch_scopus.total_results(data) == 42
    assert len(fetch_scopus.entries(data)) == 1


def test_fetch_page_uses_contract_params(monkeypatch):
    seen = {}

    class FakeResp:
        def read(self):
            return json.dumps({"search-results": {"opensearch:totalResults": "1",
                                                  "entry": []}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return FakeResp()

    monkeypatch.setattr(fetch_scopus.urllib.request, "urlopen", fake_urlopen)
    fetch_scopus.fetch_page("TITLE-ABS-KEY(test)", "k")
    assert "count=25" in seen["url"]
    assert "sort=relevance" in seen["url"]
    assert "view=COMPLETE" in seen["url"]
    assert "TITLE-ABS-KEY%28test%29" in seen["url"] or "TITLE-ABS-KEY(test)" in seen["url"]


def test_cmd_search_writes_raw(tmp_path, monkeypatch):
    out = tmp_path / "raw.json"
    data = {"search-results": {"opensearch:totalResults": "3",
                               "entry": [{"eid": "1"}]}}

    class FakeResp:
        def read(self):
            return json.dumps(data).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(fetch_scopus.urllib.request, "urlopen",
                        lambda req, timeout: FakeResp())
    monkeypatch.setenv("SCOPUS_API_KEY", "k")
    args = type("A", (), {})()
    args.query = "TITLE-ABS-KEY(x)"
    args.out = str(out)
    args.env_file = None
    rc = fetch_scopus.cmd_search(args)
    assert rc == 0
    assert json.loads(out.read_text(encoding="utf-8"))["search-results"]["entry"][0]["eid"] == "1"


def test_429_final_backoff_is_followed_by_actual_retry(monkeypatch):
    import urllib.error
    attempts, delays = [], []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self):
            return b'{"search-results":{"opensearch:totalResults":"0"}}'
    def open_request(req, timeout):
        attempts.append(1)
        if len(attempts) <= 3:
            raise urllib.error.HTTPError(req.full_url, 429, 'limited', {}, None)
        return Response()
    monkeypatch.setattr(fetch_scopus.urllib.request, 'urlopen', open_request)
    monkeypatch.setattr(fetch_scopus.time, 'sleep', delays.append)
    assert fetch_scopus.total_results(fetch_scopus.fetch_page('q', 'dummy')) == 0
    assert len(attempts) == 4 and delays == [15, 30, 60]


def test_401_does_not_backoff(monkeypatch):
    import pytest
    import urllib.error
    def fail(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, 'unauthorized', {}, None)
    monkeypatch.setattr(fetch_scopus.urllib.request, 'urlopen', fail)
    monkeypatch.setattr(fetch_scopus.time, 'sleep', lambda _: pytest.fail('nonretryable request slept'))
    with pytest.raises(urllib.error.HTTPError):
        fetch_scopus.fetch_page('q', 'dummy')
