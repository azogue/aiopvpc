"""Tests for aiopvpc."""
import json
import pathlib
from datetime import date, datetime

TEST_EXAMPLES_PATH = pathlib.Path(__file__).parent / "api_examples"

FIXTURE_JSON_DATA_2019_10_26 = "PVPC_CURV_DD_2019_10_26.json"
FIXTURE_JSON_DATA_2019_10_27 = "PVPC_CURV_DD_2019_10_27.json"
FIXTURE_JSON_DATA_2019_03_31 = "PVPC_CURV_DD_2019_03_31.json"

_DEFAULT_EMPTY_VALUE = {"message": "No values for specified archive"}


class MockAsyncSession:
    """Mock GET requests to esios API."""

    status: int = 200
    _counter: int = 0
    _raw_response = None

    def __init__(self, status=200, exc=None):
        """Set up desired mock response"""
        self._raw_response = _DEFAULT_EMPTY_VALUE
        self.status = status
        self.exc = exc

        self.responses = {
            date(2019, 3, 31): load_fixture(FIXTURE_JSON_DATA_2019_03_31),
            date(2019, 10, 26): load_fixture(FIXTURE_JSON_DATA_2019_10_26),
            date(2019, 10, 27): load_fixture(FIXTURE_JSON_DATA_2019_10_27),
        }

    async def json(self, *_args, **_kwargs):
        """Dumb await."""
        return self._raw_response

    async def get(self, url, *_args, **_kwargs):
        """Dumb await."""
        self._counter += 1
        day = datetime.fromisoformat(url.split("=")[-1]).date()
        if self.exc:
            raise self.exc
        if day in self.responses:
            self._raw_response = self.responses[day]
        else:
            self._raw_response = _DEFAULT_EMPTY_VALUE
        return self

    @property
    def call_count(self) -> int:
        """Return call counter."""
        return self._counter


def load_fixture(filename: str):
    """Load stored example for esios API response."""
    return json.loads((TEST_EXAMPLES_PATH / filename).read_text())
