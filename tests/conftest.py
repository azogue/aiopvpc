"""Tests for aiopvpc."""
from __future__ import annotations

import json
import logging
import pathlib
import zoneinfo
from datetime import date, datetime, timedelta

from aiopvpc.const import ESIOS_INJECTION, ESIOS_MAG, ESIOS_OMIE, ESIOS_PVPC, KEY_PVPC
from aiopvpc.pvpc_data import EsiosApiData, PVPCData

TEST_EXAMPLES_PATH = pathlib.Path(__file__).parent / "api_examples"
TZ_TEST = zoneinfo.ZoneInfo("Atlantic/Canary")

_FIXTURE_DATA_2021_10_30 = "PVPC_CURV_DD_2021_10_30.json"
_FIXTURE_DATA_2021_10_31 = "PVPC_CURV_DD_2021_10_31.json"
_FIXTURE_DATA_2022_03_27 = "PVPC_CURV_DD_2022_03_27.json"
_FIXTURE_DATA_2021_06_01 = "PVPC_CURV_DD_2021_06_01.json"
_FIXTURE_ESIOS_PVPC_2021_10_30 = "PRICES_ESIOS_1001_2021_10_30.json"
_FIXTURE_ESIOS_PVPC_2021_10_31 = "PRICES_ESIOS_1001_2021_10_31.json"
_FIXTURE_ESIOS_PVPC_2021_06_01 = "PRICES_ESIOS_1001_2021_06_01.json"
_FIXTURE_ESIOS_PVPC_2023_01_06 = "PRICES_ESIOS_1001_2023_01_06.json"
_FIXTURE_ESIOS_INJECTION_2021_10_30 = "PRICES_ESIOS_1739_2021_10_30.json"
_FIXTURE_ESIOS_INJECTION_2021_10_31 = "PRICES_ESIOS_1739_2021_10_31.json"
_FIXTURE_ESIOS_INJECTION_2023_01_06 = "PRICES_ESIOS_1739_2023_01_06.json"
_FIXTURE_ESIOS_OMIE_2021_10_30 = "PRICES_ESIOS_10211_2021_10_30.json"
_FIXTURE_ESIOS_OMIE_2021_10_31 = "PRICES_ESIOS_10211_2021_10_31.json"
_FIXTURE_ESIOS_OMIE_2023_01_06 = "PRICES_ESIOS_10211_2023_01_06.json"
_FIXTURE_ESIOS_MAG_2023_01_06 = "PRICES_ESIOS_1900_2023_01_06.json"

_DEFAULT_EMPTY_VALUE = {"message": "No values for specified archive"}
_DEFAULT_UNAUTH_MSG = "HTTP Token: Access denied (TEST)."


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

        self.responses_public = {
            date(2022, 3, 27): load_fixture(_FIXTURE_DATA_2022_03_27),
            date(2021, 10, 30): load_fixture(_FIXTURE_DATA_2021_10_30),
            date(2021, 10, 31): load_fixture(_FIXTURE_DATA_2021_10_31),
            date(2021, 6, 1): load_fixture(_FIXTURE_DATA_2021_06_01),
        }
        self.responses_token = {
            ESIOS_PVPC: {
                date(2021, 10, 30): load_fixture(_FIXTURE_ESIOS_PVPC_2021_10_30),
                date(2021, 10, 31): load_fixture(_FIXTURE_ESIOS_PVPC_2021_10_31),
                date(2021, 6, 1): load_fixture(_FIXTURE_ESIOS_PVPC_2021_06_01),
                date(2023, 1, 6): load_fixture(_FIXTURE_ESIOS_PVPC_2023_01_06),
            },
            ESIOS_INJECTION: {
                date(2021, 10, 30): load_fixture(_FIXTURE_ESIOS_INJECTION_2021_10_30),
                date(2021, 10, 31): load_fixture(_FIXTURE_ESIOS_INJECTION_2021_10_31),
                date(2023, 1, 6): load_fixture(_FIXTURE_ESIOS_INJECTION_2023_01_06),
            },
            ESIOS_MAG: {
                date(2023, 1, 6): load_fixture(_FIXTURE_ESIOS_MAG_2023_01_06),
            },
            ESIOS_OMIE: {
                date(2021, 10, 30): load_fixture(_FIXTURE_ESIOS_OMIE_2021_10_30),
                date(2021, 10, 31): load_fixture(_FIXTURE_ESIOS_OMIE_2021_10_31),
                date(2023, 1, 6): load_fixture(_FIXTURE_ESIOS_OMIE_2023_01_06),
            },
        }

    async def json(self, *_args, **_kwargs):
        """Dumb await."""
        return self._raw_response

    async def get(self, url: str, *_args, **_kwargs):
        """Dumb await."""
        self._counter += 1
        if self.exc:
            raise self.exc

        prefix_public = "https://api.esios.ree.es/archives/"
        prefix_token = "https://api.esios.ree.es/indicators/"
        key = datetime.fromisoformat(url.split("=")[-1]).date()
        if url.startswith(prefix_token):
            indicator = url.removeprefix(prefix_token).split("?")[0]
            self._raw_response = self.responses_token.get(indicator, {}).get(
                key, _DEFAULT_UNAUTH_MSG
            )
        elif url.startswith(prefix_public) and key in self.responses_public:
            self._raw_response = self.responses_public[key]
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


async def run_h_step(
    mock_session: MockAsyncSession,
    pvpc_data: PVPCData,
    api_data: EsiosApiData | None,
    start: datetime,
    should_fail: bool = False,
) -> tuple[datetime, EsiosApiData]:
    current_prices = api_data.sensors[KEY_PVPC] if api_data else {}
    if current_prices:
        logging.debug(
            "[Calls=%d]-> start=%s --> %s -> %s (%d prices)",
            mock_session.call_count,
            start,
            list(current_prices)[0].strftime("%Y-%m-%d %Hh"),
            list(current_prices)[-1].strftime("%Y-%m-%d %Hh"),
            len(current_prices),
        )
    api_data = await pvpc_data.async_update_all(api_data, start)
    state_ok = pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, start)
    assert should_fail is not state_ok
    start += timedelta(hours=1)
    return start, api_data


def check_num_datapoints(
    api_data: EsiosApiData, sensor_keys: tuple[str, ...], expected: int
):
    for key in sensor_keys:
        num_points = len(api_data.sensors[key])
        assert num_points == expected, (key, expected, num_points)
