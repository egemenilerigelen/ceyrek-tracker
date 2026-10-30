import pytest
import requests

from ceyrek_tracker.infra.http import ProviderError, get_json


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TestGetJson:
    def test_retries_truncated_body(self):
        # Truncgil'in zaman zaman yaptığı gibi: 200 + yarım JSON, sonra düzgün yanıt.
        session = _FakeSession([_FakeResponse(b'{"a": "yar'), _FakeResponse(b'{"a": 1}')])
        assert get_json(session, "https://x") == {"a": 1}
        assert session.calls == 2

    def test_gives_up_after_attempts(self):
        session = _FakeSession([_FakeResponse(b"{")] * 3)
        with pytest.raises(ProviderError):
            get_json(session, "https://x", attempts=3)

    def test_wraps_connection_errors(self):
        session = _FakeSession([requests.ConnectionError("koptu")])
        with pytest.raises(ProviderError, match="Bağlantı"):
            get_json(session, "https://x")

    def test_http_error_is_provider_error(self):
        session = _FakeSession([_FakeResponse(b"", status=503)])
        with pytest.raises(ProviderError):
            get_json(session, "https://x")
