import json
from pathlib import Path

from app.collectors.cninfo import CNInfoCollector


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_cninfo_collector_returns_limited_announcements(monkeypatch) -> None:
    fixture = json.loads((FIXTURE_DIR / "cninfo_announcements.json").read_text(encoding="utf-8"))

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return fixture

    def fake_post(url, data, headers, timeout):
        assert "stock" in data
        assert headers["X-Requested-With"] == "XMLHttpRequest"
        return FakeResponse()

    monkeypatch.setattr("app.collectors.cninfo.requests.post", fake_post)

    collector = CNInfoCollector()
    items = collector.fetch_events("000001", limit=1)

    assert len(items) == 1
    assert items[0]["announcementId"] == "123"
