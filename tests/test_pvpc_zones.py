"""Tests for aiopvpc."""

from datetime import datetime
from typing import cast

import pytest

from aiopvpc.const import DataSource, KEY_PVPC, REFERENCE_TZ, TARIFFS, UTC_TZ
from aiopvpc.parser import extract_prices_from_esios_token
from aiopvpc.pvpc_data import PVPCData
from tests.conftest import load_fixture, MockAsyncSession, TZ_TEST


@pytest.mark.parametrize(
    "local_tz, source, tariff, geo_zone, expected_18h",
    (
        (TZ_TEST, "esios_public", TARIFFS[0], None, 0.23144),
        (REFERENCE_TZ, "esios_public", TARIFFS[0], None, 0.23144),
        (REFERENCE_TZ, "esios_public", TARIFFS[1], None, 0.13813),
        (REFERENCE_TZ, "esios", TARIFFS[0], None, 0.23144),
        (REFERENCE_TZ, "esios", TARIFFS[1], None, 0.13813),
        (TZ_TEST, "esios", TARIFFS[0], None, 0.23144),
        (REFERENCE_TZ, "esios", TARIFFS[0], "Baleares", 0.23144),
        (REFERENCE_TZ, "esios", TARIFFS[1], "Melilla", 0.13813),
    ),
)
@pytest.mark.asyncio
async def test_geo_ids(local_tz, source, tariff, geo_zone, expected_18h):
    """Test different prices for different geo zones."""
    start = datetime(2021, 6, 1, 10, tzinfo=UTC_TZ)
    mock_session = MockAsyncSession()
    pvpc_data = PVPCData(
        session=mock_session,
        tariff=tariff,
        local_timezone=local_tz,
        data_source=cast("DataSource", source),
        api_token="test-token" if source == "esios" else None,
        geo_zone=geo_zone,
    )
    api_data = await pvpc_data.async_update_all(None, start)
    assert all(api_data.availability.values())
    assert pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, start)
    ts_loc_18h_utc = datetime(2021, 6, 1, 18, tzinfo=local_tz).astimezone(UTC_TZ)
    price_loc_18h = api_data.sensors[KEY_PVPC][ts_loc_18h_utc]
    assert price_loc_18h == expected_18h


def test_invalid_geo_zone_raises():
    """Verify explicit invalid geozone raises ValueError."""
    mock_session = MockAsyncSession()
    with pytest.raises(ValueError, match="Unknown geozone"):
        PVPCData(session=mock_session, geo_zone="Unknown")


def test_extract_esios_token_unknown_geoid_and_non_mutating():
    """Verify unknown geo_id does not raise and input dict is not mutated."""
    data = load_fixture("PRICES_ESIOS_1001_2024_03_09.json")
    data["indicator"]["values"].append(
        {
            "value": 100.0,
            "datetime": "2024-03-09T00:00:00.000+01:00",
            "datetime_utc": "2024-03-08T23:00:00Z",
            "tz_time": "2024-03-08T23:00:00.000Z",
            "geo_id": 9999,
            "geo_name": "Unknown",
        }
    )
    parsed = extract_prices_from_esios_token(data, KEY_PVPC, "Península")
    assert "indicator" in data
    assert len(parsed.series[KEY_PVPC]) == 24
