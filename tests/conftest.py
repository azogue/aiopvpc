"""Tests for aiopvpc."""
import json
import pathlib
import sys
from datetime import date, datetime

if sys.version_info[:2] >= (3, 9):
    import zoneinfo  # pylint: disable=import-error
else:
    from backports import zoneinfo  # type: ignore

TEST_EXAMPLES_PATH = pathlib.Path(__file__).parent / "api_examples"
TZ_TEST = zoneinfo.ZoneInfo("Atlantic/Canary")

FIXTURE_JSON_DATA_2021_10_30 = "PVPC_CURV_DD_2021_10_30.json"
FIXTURE_JSON_DATA_2021_10_31 = "PVPC_CURV_DD_2021_10_31.json"
FIXTURE_JSON_DATA_2022_03_27 = "PVPC_CURV_DD_2022_03_27.json"
FIXTURE_JSON_DATA_2021_06_01 = "PVPC_CURV_DD_2021_06_01.json"
FIXTURE_JSON_DATA_S2_2021_06_01 = "PRICES_APIDATOS_2021_06_01.json"
FIXTURE_JSON_DATA_S2_2021_06_01_CYM = "PRICES_APIDATOS_2021_06_01_CYM.json"
FIXTURE_JSON_DATA_S2_2021_10_30 = "PRICES_APIDATOS_2021_10_30.json"
FIXTURE_JSON_DATA_S2_2021_10_31 = "PRICES_APIDATOS_2021_10_31.json"

_DEFAULT_EMPTY_VALUE = {"message": "No values for specified archive"}


class MockAsyncSession:
    """Mock GET requests to esios API."""

    status: int = 200
    _counter: int = 0
    _raw_response = None

    def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __await__(self):
        yield
        return self

    async def close(self, *_args):
        pass

    def __init__(self, status=200, exc=None):
        """Set up desired mock response"""
        self._raw_response = _DEFAULT_EMPTY_VALUE
        self.status = status
        self.exc = exc

        self.responses_apidatos = {
            "CYM_PRICES": load_fixture(FIXTURE_JSON_DATA_S2_2021_06_01_CYM),
            date(2021, 10, 30): load_fixture(FIXTURE_JSON_DATA_S2_2021_10_30),
            date(2021, 10, 31): load_fixture(FIXTURE_JSON_DATA_S2_2021_10_31),
            date(2021, 6, 1): load_fixture(FIXTURE_JSON_DATA_S2_2021_06_01),
        }
        self.responses_esios = {
            date(2022, 3, 27): load_fixture(FIXTURE_JSON_DATA_2022_03_27),
            date(2021, 10, 30): load_fixture(FIXTURE_JSON_DATA_2021_10_30),
            date(2021, 10, 31): load_fixture(FIXTURE_JSON_DATA_2021_10_31),
            date(2021, 6, 1): load_fixture(FIXTURE_JSON_DATA_2021_06_01),
        }

    async def json(self, *_args, **_kwargs):
        """Dumb await."""
        return self._raw_response

    async def get(self, url, *_args, **_kwargs):
        """Dumb await."""
        self._counter += 1
        if self.exc:
            raise self.exc
        key = datetime.fromisoformat(url.split("=")[-1]).date()
        if key == date(2021, 6, 1) and "geo_ids=8744" in url:
            assert url.startswith("https://apidatos.ree.es")
            self._raw_response = self.responses_apidatos["CYM_PRICES"]
        elif (
            url.startswith("https://api.esios.ree.es/archives")
            and key in self.responses_esios
        ):
            self._raw_response = self.responses_esios[key]
        elif (
            url.startswith("https://apidatos.ree.es") and key in self.responses_apidatos
        ):
            self._raw_response = self.responses_apidatos[key]
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
