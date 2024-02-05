"""
Simple aio library to download Spanish electricity hourly prices.

* URL for JSON daily files
* Parser for the contents of the JSON files
"""

from datetime import datetime, timedelta
from itertools import groupby
from operator import itemgetter
from typing import Any

from aiopvpc.const import (
    DataSource,
    EsiosResponse,
    GEOZONE_ID2NAME,
    GEOZONES,
    KEY_PVPC,
    PRICE_PRECISION,
    REFERENCE_TZ,
    SENSOR_KEY_TO_DATAID,
    TARIFF2ID,
    TARIFFS,
    URL_ESIOS_TOKEN_RESOURCE,
    URL_PUBLIC_PVPC_RESOURCE,
    UTC_TZ,
    zoneinfo,
)


def _timezone_offset(tz: zoneinfo.ZoneInfo = REFERENCE_TZ) -> timedelta:
    ref_ts = datetime(2021, 1, 1, tzinfo=REFERENCE_TZ).astimezone(UTC_TZ)
    loc_ts = datetime(2021, 1, 1, tzinfo=tz).astimezone(UTC_TZ)
    return loc_ts - ref_ts


def extract_prices_from_esios_public(
    data: dict[str, Any], key: str, tz: zoneinfo.ZoneInfo = REFERENCE_TZ
) -> EsiosResponse:
    """Parse the contents of a daily PVPC json file."""
    ts_init = datetime(
        *datetime.strptime(data["PVPC"][0]["Dia"], "%d/%m/%Y").timetuple()[:3],
        tzinfo=tz,
    ).astimezone(UTC_TZ)

    def _parse_tariff_val(value, prec=PRICE_PRECISION) -> float:
        return round(float(value.replace(",", ".")) / 1000.0, prec)

    pvpc_prices = {
        ts_init + timedelta(hours=i): _parse_tariff_val(values_hour[key])
        for i, values_hour in enumerate(data["PVPC"])
    }

    return EsiosResponse(
        name="PVPC ESIOS",
        data_id="legacy",
        last_update=datetime.utcnow().replace(microsecond=0, tzinfo=UTC_TZ),
        unit="€/kWh",
        series={KEY_PVPC: pvpc_prices},
    )


def extract_prices_from_esios_token(
    data: dict[str, Any],
    sensor_key: str,
    geo_zone: str,
    tz: zoneinfo.ZoneInfo = REFERENCE_TZ,
) -> EsiosResponse:
    """Parse the contents of an 'indicator' json file from ESIOS API."""
    offset_timezone = _timezone_offset(tz)
    indicator_data = data.pop("indicator")
    unit = "•".join(mag["name"] for mag in indicator_data["magnitud"])
    unit_tiempo = "•".join(mag["name"] for mag in indicator_data["tiempo"])
    unit += f"/{unit_tiempo}"
    ts_update = datetime.utcnow().replace(microsecond=0, tzinfo=UTC_TZ)

    def _parse_dt(ts: str) -> datetime:
        return datetime.fromisoformat(ts).astimezone(UTC_TZ) + offset_timezone

    def _value_unit_conversion(value: float) -> float:
        # from €/MWh to €/kWh
        return round(float(value) / 1000.0, 5)

    value_gen = groupby(
        sorted(indicator_data["values"], key=itemgetter("geo_id")),
        itemgetter("geo_id"),
    )
    parsed_data = {
        GEOZONE_ID2NAME[key]: {
            _parse_dt(item["datetime"]): _value_unit_conversion(item["value"])
            for item in list(group)
        }
        for key, group in value_gen
    }
    if geo_zone in parsed_data:
        geo_data = parsed_data[geo_zone]
    elif "Península" in parsed_data:
        geo_data = parsed_data["Península"]
    else:
        geo_data = parsed_data["España"]

    return EsiosResponse(
        name=indicator_data["name"],
        data_id=str(indicator_data["id"]),
        last_update=ts_update,
        unit=unit,
        series={sensor_key: geo_data},
    )


def extract_esios_data(
    data: dict[str, Any],
    url: str,
    sensor_key: str,
    tariff: str,
    tz: zoneinfo.ZoneInfo = REFERENCE_TZ,
) -> EsiosResponse:
    """Parse the contents of a daily PVPC json file."""
    if url.startswith("https://api.esios.ree.es/archives"):
        return extract_prices_from_esios_public(data, TARIFF2ID[tariff], tz)

    if url.startswith("https://api.esios.ree.es/indicators"):
        # TODO adapt better to geozones
        if tariff == TARIFFS[0] and tz != REFERENCE_TZ:
            geo_zone = GEOZONES[1]
        elif tariff == TARIFFS[0]:
            geo_zone = GEOZONES[0]
        else:
            geo_zone = GEOZONES[3]

        return extract_prices_from_esios_token(data, sensor_key, geo_zone, tz)
    raise NotImplementedError(f"Data source not known: {url} >{data}")


def get_daily_urls_to_download(
    source: DataSource,
    sensor_keys: set[str],
    now_local_ref: datetime,
    next_day_local_ref: datetime,
) -> tuple[list[str], list[str]]:
    """Make URLs for ESIOS price series."""
    if source == "esios_public":
        assert sensor_keys == {KEY_PVPC}
        return (
            [URL_PUBLIC_PVPC_RESOURCE.format(day=now_local_ref.date())],
            [URL_PUBLIC_PVPC_RESOURCE.format(day=next_day_local_ref.date())],
        )

    assert source == "esios"
    today = [
        URL_ESIOS_TOKEN_RESOURCE.format(
            ind=SENSOR_KEY_TO_DATAID[key], day=now_local_ref.date()
        )
        for key in sensor_keys
    ]
    tomorrow = [
        URL_ESIOS_TOKEN_RESOURCE.format(
            ind=SENSOR_KEY_TO_DATAID[key], day=next_day_local_ref.date()
        )
        for key in sensor_keys
    ]
    return today, tomorrow
