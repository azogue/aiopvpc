"""Tests for aiopvpc."""

from datetime import date, datetime, timedelta
from typing import cast

import pytest

from aiopvpc.const import (
    ALL_SENSORS,
    DataSource,
    ESIOS_PVPC,
    KEY_ADJUSTMENT,
    KEY_INJECTION,
    KEY_MAG,
    KEY_OMIE,
    KEY_PVPC,
    REFERENCE_TZ,
    SENSOR_KEY_TO_DATAID,
)
from aiopvpc.parser import (
    extract_prices_from_esios_public,
    extract_prices_from_esios_token,
    get_daily_urls_to_download,
)
from aiopvpc.prices import _is_tomorrow_price
from aiopvpc.pvpc_data import PVPCData
from tests.conftest import MockAsyncSession, TZ_TEST


@pytest.mark.parametrize(
    "ts, source, timezone, n_prices, n_calls, n_prices_8h, available_8h",
    (
        ("2021-06-01 09:00:00", "esios", REFERENCE_TZ, 24, 1, 24, True),
        ("2021-06-01 09:00:00", "esios", TZ_TEST, 24, 1, 24, True),
        ("2024-03-09 09:00:00", "esios", REFERENCE_TZ, 24, 1, 24, True),
        ("2024-03-09 09:00:00", "esios", TZ_TEST, 24, 1, 24, True),
        ("2021-10-30 00:00:00+08:00", "esios_public", TZ_TEST, 0, 1, 0, False),
        ("2021-10-30 00:00:00", "esios_public", TZ_TEST, 24, 1, 24, True),
        ("2021-10-31 00:00:00", "esios_public", TZ_TEST, 25, 1, 25, True),
        ("2022-03-27 20:00:00", "esios_public", TZ_TEST, 23, 2, 23, False),
        ("2022-03-27 20:00:00+04:00", "esios_public", TZ_TEST, 23, 1, 23, False),
        ("2021-10-30 21:00:00", "esios_public", TZ_TEST, 49, 2, 26, True),
        ("2021-10-30 21:00:00+01:00", "esios_public", TZ_TEST, 49, 2, 26, True),
        ("2021-10-30 00:00:00", "esios_public", REFERENCE_TZ, 24, 1, 24, True),
        ("2021-10-31 00:00:00", "esios_public", REFERENCE_TZ, 25, 1, 25, True),
        ("2022-03-27 20:00:00", "esios_public", REFERENCE_TZ, 23, 2, 23, False),
        ("2021-10-30 21:00:00", "esios_public", REFERENCE_TZ, 49, 2, 25, True),
        ("2021-06-01 09:00:00", "esios_public", REFERENCE_TZ, 24, 1, 24, True),
        ("2021-06-01 09:00:00", "esios_public", TZ_TEST, 24, 1, 24, True),
    ),
)
@pytest.mark.asyncio
async def test_price_extract(
    ts,
    source,
    timezone,
    n_prices,
    n_calls,
    n_prices_8h,
    available_8h,
):
    """Test data parsing of official API files."""
    day = datetime.fromisoformat(ts)
    mock_session = MockAsyncSession()

    pvpc_data = PVPCData(
        session=mock_session,
        tariff="2.0TD",
        local_timezone=timezone,
        data_source=cast("DataSource", source),
        api_token="test-token" if source == "esios" else None,
    )

    api_data = await pvpc_data.async_update_all(None, day)
    pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, day)
    assert len(api_data.sensors[KEY_PVPC]) == n_prices
    assert mock_session.call_count == n_calls
    assert len(api_data.sensors) == 1

    has_prices = pvpc_data.process_state_and_attributes(
        api_data, KEY_PVPC, day + timedelta(hours=10)
    )
    assert len(api_data.sensors[KEY_PVPC]) == n_prices_8h
    assert has_prices == available_8h
    if has_prices:
        last_dt, _ = list(api_data.sensors[KEY_PVPC].items())[-1]
        assert last_dt.astimezone(timezone).hour == 23


@pytest.mark.asyncio
async def test_price_sensor_attributes():
    """Test data parsing of official API files."""
    day = datetime.fromisoformat("2024-03-09 09:00:00")
    mock_session = MockAsyncSession()

    pvpc_data = PVPCData(
        session=mock_session,
        tariff="2.0TD",
        api_token="test-token",
        sensor_keys=ALL_SENSORS,
    )

    api_data = await pvpc_data.async_update_all(None, day)
    for key in ALL_SENSORS:
        pvpc_data.process_state_and_attributes(api_data, key, day)
    assert len(api_data.sensors[KEY_PVPC]) == 24
    assert mock_session.call_count == 5
    assert len(api_data.sensors) == 6

    ref_data = {
        KEY_PVPC: {"hours_to_better_price": 1, "num_better_prices_ahead": 3},
        KEY_INJECTION: {"hours_to_better_price": 6, "num_better_prices_ahead": 6},
        KEY_MAG: {"hours_to_better_price": 1, "num_better_prices_ahead": 11},
        KEY_OMIE: {"hours_to_better_price": 1, "num_better_prices_ahead": 4},
        KEY_ADJUSTMENT: {"hours_to_better_price": 1, "num_better_prices_ahead": 2},
    }

    for key in ALL_SENSORS:
        has_prices = pvpc_data.process_state_and_attributes(
            api_data, key, day + timedelta(hours=2)
        )
        assert has_prices, key
        assert api_data.availability[key]
        last_dt, last_p = list(api_data.sensors[key].items())[-1]
        assert last_dt.astimezone(REFERENCE_TZ).hour == 23

        current_price = pvpc_data.states[key]
        sensor_attrs = pvpc_data.sensor_attributes[key]
        assert sensor_attrs["sensor_id"] == key
        assert sensor_attrs["data_id"] == SENSOR_KEY_TO_DATAID.get(key, "composed")
        assert sensor_attrs["price_12h"] == current_price
        prices_ahead = [sensor_attrs[f"price_{h:02}h"] for h in range(13, 24)]
        assert len(prices_ahead) == 11
        assert sensor_attrs["price_23h"] == last_p
        assert sensor_attrs["min_price"] == min(api_data.sensors[key].values())
        assert sensor_attrs["max_price"] == max(api_data.sensors[key].values())
        key_min_at = f"price_{sensor_attrs['min_price_at']:02d}h"
        assert sensor_attrs[key_min_at] == min(api_data.sensors[key].values())
        key_max_at = f"price_{sensor_attrs['max_price_at']:02d}h"
        assert sensor_attrs[key_max_at] == max(api_data.sensors[key].values())
        assert (
            sensor_attrs["hours_to_better_price"]
            == ref_data[key]["hours_to_better_price"]
        )
        assert (
            sensor_attrs["num_better_prices_ahead"]
            == ref_data[key]["num_better_prices_ahead"]
        )
        key_next = f"price_{12 + sensor_attrs['hours_to_better_price']}h"
        if key == KEY_INJECTION:
            assert sensor_attrs[key_next] > current_price
            num_better = sum(1 for p in prices_ahead if p > current_price)
        else:
            assert sensor_attrs[key_next] < current_price
            num_better = sum(1 for p in prices_ahead if p < current_price)
        assert num_better == sensor_attrs["num_better_prices_ahead"]


def _make_quarter_hourly_indicator_payload(target_day: date) -> dict:
    """Build synthetic 96-slot (15-min) ESIOS indicator payload for a single day."""
    start = datetime(
        target_day.year, target_day.month, target_day.day, tzinfo=REFERENCE_TZ
    )
    values = [
        {
            "value": float(100 + i),
            "datetime": (start + timedelta(minutes=15 * i)).isoformat(),
            "geo_id": 8741,
            "geo_name": "Península",
        }
        for i in range(96)
    ]
    return {
        "indicator": {
            "id": 1001,
            "name": "PVPC 15min",
            "magnitud": [{"name": "EUR"}],
            "tiempo": [{"name": "Cuarto de hora"}],
            "values": values,
        }
    }


@pytest.mark.asyncio
async def test_quarter_hourly_parsing_and_scheduling():
    """Verify 15-minute slot parsing, attribute keys, and 20:00 next-day fetch."""
    day1 = date(2026, 1, 15)
    day2 = date(2026, 1, 16)
    payload_day1 = _make_quarter_hourly_indicator_payload(day1)
    parsed = extract_prices_from_esios_token(payload_day1, KEY_PVPC, "Península")
    assert len(parsed.series[KEY_PVPC]) == 96

    mock_session = MockAsyncSession()
    mock_session.responses_token[ESIOS_PVPC][day1] = payload_day1
    mock_session.responses_token[ESIOS_PVPC][day2] = (
        _make_quarter_hourly_indicator_payload(day2)
    )
    pvpc_data = PVPCData(
        session=mock_session,
        tariff="2.0TD",
        local_timezone=REFERENCE_TZ,
        data_source="esios",
        api_token="test-token",
    )

    morning = datetime(2026, 1, 15, 10, 0, tzinfo=REFERENCE_TZ)
    api_data = await pvpc_data.async_update_all(None, morning)
    assert mock_session.call_count == 1
    assert len(api_data.sensors[KEY_PVPC]) == 96

    # Check 15-minute slot snapping (:00, :15, :30, :45)
    for minute, key_name, expected_idx in (
        (5, "price_10h", 40),
        (22, "price_10h15", 41),
        (37, "price_10h30", 42),
        (59, "price_10h45", 43),
    ):
        ts = datetime(2026, 1, 15, 10, minute, tzinfo=REFERENCE_TZ)
        assert pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, ts)
        expected_price = round((100 + expected_idx) / 1000.0, 5)
        assert pvpc_data.states[KEY_PVPC] == expected_price
        assert pvpc_data.sensor_attributes[KEY_PVPC][key_name] == expected_price
        assert len(api_data.sensors[KEY_PVPC]) == 96

    # Check minutes_to_better_price when a cheaper 15-min slot is ahead
    api_data.sensors[KEY_PVPC][
        datetime(2026, 1, 15, 10, 15, tzinfo=REFERENCE_TZ).astimezone()
    ] = 0.05
    ts_10_00 = datetime(2026, 1, 15, 10, 0, tzinfo=REFERENCE_TZ)
    assert pvpc_data.process_state_and_attributes(api_data, KEY_PVPC, ts_10_00)
    assert pvpc_data.sensor_attributes[KEY_PVPC]["minutes_to_better_price"] == 15

    # At 20:00 with 96 today slots, must still fetch tomorrow's prices
    evening_20 = datetime(2026, 1, 15, 20, 0, tzinfo=REFERENCE_TZ)
    api_data = await pvpc_data.async_update_all(api_data, evening_20)
    assert mock_session.call_count == 2
    assert len(api_data.sensors[KEY_PVPC]) == 192

    # Subsequent evening call avoids redundant requests
    evening_21 = datetime(2026, 1, 15, 21, 0, tzinfo=REFERENCE_TZ)
    api_data = await pvpc_data.async_update_all(api_data, evening_21)
    assert mock_session.call_count == 2


def test_is_tomorrow_price_and_public_tah_and_geo_urls():
    """Verify _is_tomorrow_price edge cases, public TAH parsing, and geo_ids[] URLs."""
    # Past date in previous week with higher weekday must NOT be tomorrow
    ref_mon = datetime(2026, 11, 16, 10, tzinfo=REFERENCE_TZ)
    past_tue = datetime(2026, 11, 10, 10, tzinfo=REFERENCE_TZ)
    next_tue = datetime(2026, 11, 17, 0, tzinfo=REFERENCE_TZ)
    assert not _is_tomorrow_price(past_tue, ref_mon)
    assert not _is_tomorrow_price(ref_mon, ref_mon)
    assert _is_tomorrow_price(next_tue, ref_mon)
    # Year rollover
    assert _is_tomorrow_price(
        datetime(2027, 1, 1, 0, tzinfo=REFERENCE_TZ),
        datetime(2026, 12, 31, 23, tzinfo=REFERENCE_TZ),
    )

    # Public archive with 2026 TAHPCB field parses both PVPC and ADJUSTMENT
    public_payload = {
        "PVPC": [
            {"Dia": "20/11/2026", "Hora": "00-01", "PCB": "78,63", "TAHPCB": "-36,42"},
            {"Dia": "20/11/2026", "Hora": "01-02", "PCB": "70,00", "TAHPCB": "-30,00"},
        ]
    }
    parsed = extract_prices_from_esios_public(public_payload, "PCB", REFERENCE_TZ)
    assert KEY_PVPC in parsed.series
    assert KEY_ADJUSTMENT in parsed.series
    assert list(parsed.series[KEY_ADJUSTMENT].values()) == [-0.03642, -0.03]

    # Server-side geo_ids[] filtering applies only to multi-geozone indicators
    now_ref = datetime(2026, 11, 20, 10, tzinfo=REFERENCE_TZ)
    next_ref = now_ref + timedelta(days=1)
    today_urls, _ = get_daily_urls_to_download(
        "esios",
        {KEY_PVPC, KEY_INJECTION, KEY_OMIE, KEY_ADJUSTMENT},
        now_ref,
        next_ref,
        geo_zone="Canarias",
    )
    by_ind = {u.split("/indicators/")[1].split("?")[0]: u for u in today_urls}
    assert "geo_ids[]=8742&" in by_ind["1001"]
    assert "geo_ids[]=8742&" in by_ind["2108"]
    assert "geo_ids[]" not in by_ind["1739"]
    assert "geo_ids[]" not in by_ind["10211"]
