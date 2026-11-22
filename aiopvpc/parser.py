"""
Simple aio library to download Spanish electricity hourly prices.

* URL for JSON daily files
* Parser for the contents of the JSON files
"""

from datetime import datetime, timedelta, UTC
from itertools import groupby
from operator import itemgetter
from typing import Any

from aiopvpc.const import (
    CANARY_TZ,
    DataSource,
    ESIOS_MULTI_GEOZONE_INDICATORS,
    EsiosResponse,
    GEOZONE_ID2NAME,
    GEOZONE_NAME2ID,
    GEOZONES,
    KEY_ADJUSTMENT,
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


def resolve_geo_zone(
    tariff: str,
    tz: zoneinfo.ZoneInfo,
    geo_zone: str | None = None,
) -> str:
    """Resolve ESIOS geozone name from explicit override, tariff, and timezone."""
    if geo_zone is not None:
        if geo_zone not in GEOZONES:
            raise ValueError(
                f"Unknown geozone '{geo_zone}'. Expected one of {GEOZONES}"
            )
        return geo_zone
    if tariff != TARIFFS[0]:
        return "Ceuta"
    if tz == CANARY_TZ:
        return "Canarias"
    return "Península"


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
    series: dict[str, dict[datetime, float]] = {KEY_PVPC: pvpc_prices}
    tah_key = f"TAH{key}"
    if tah_key in data["PVPC"][0]:
        series[KEY_ADJUSTMENT] = {
            ts_init + timedelta(hours=i): _parse_tariff_val(values_hour[tah_key])
            for i, values_hour in enumerate(data["PVPC"])
        }

    return EsiosResponse(
        name="PVPC ESIOS",
        data_id="legacy",
        last_update=datetime.now(UTC).replace(microsecond=0),
        unit="€/kWh",
        series=series,
    )


def extract_prices_from_esios_token(
    data: dict[str, Any],
    sensor_key: str,
    geo_zone: str,
    tz: zoneinfo.ZoneInfo = REFERENCE_TZ,
) -> EsiosResponse:
    """Parse the contents of an 'indicator' json file from ESIOS API."""
    offset_timezone = _timezone_offset(tz)
    indicator_data = data["indicator"]
    unit = "•".join(mag["name"] for mag in indicator_data["magnitud"])
    unit_tiempo = "•".join(mag["name"] for mag in indicator_data["tiempo"])
    unit += f"/{unit_tiempo}"
    ts_update = datetime.now(UTC).replace(microsecond=0)

    def _parse_dt(ts: str) -> datetime:
        return datetime.fromisoformat(ts).astimezone(UTC_TZ) + offset_timezone

    def _value_unit_conversion(value: float) -> float:
        # from €/MWh to €/kWh
        return round(float(value) / 1000.0, PRICE_PRECISION)

    value_gen = groupby(
        sorted(indicator_data["values"], key=itemgetter("geo_id")),
        itemgetter("geo_id"),
    )
    parsed_data = {
        GEOZONE_ID2NAME.get(key, str(key)): {
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
    geo_zone: str | None = None,
) -> EsiosResponse:
    """Parse the contents of a daily PVPC json file."""
    if url.startswith("https://api.esios.ree.es/archives"):
        return extract_prices_from_esios_public(data, TARIFF2ID[tariff], tz)

    if url.startswith("https://api.esios.ree.es/indicators"):
        resolved_geo = resolve_geo_zone(tariff, tz, geo_zone)
        return extract_prices_from_esios_token(data, sensor_key, resolved_geo, tz)
    raise NotImplementedError(f"Data source not known: {url} >{data}")


def get_daily_urls_to_download(
    source: DataSource,
    sensor_keys: set[str],
    now_local_ref: datetime,
    next_day_local_ref: datetime,
    geo_zone: str | None = None,
) -> tuple[list[str], list[str]]:
    """Make URLs for ESIOS price series."""
    if source == "esios_public":
        assert sensor_keys == {KEY_PVPC}
        return (
            [URL_PUBLIC_PVPC_RESOURCE.format(day=now_local_ref.date())],
            [URL_PUBLIC_PVPC_RESOURCE.format(day=next_day_local_ref.date())],
        )

    assert source == "esios"
    geo_id = GEOZONE_NAME2ID.get(geo_zone) if geo_zone is not None else None

    def _build_token_url(key: str, target_day: datetime) -> str:
        ind = SENSOR_KEY_TO_DATAID[key]
        base = URL_ESIOS_TOKEN_RESOURCE.format(ind=ind, day=target_day.date())
        if geo_id is not None and ind in ESIOS_MULTI_GEOZONE_INDICATORS:
            return base.replace("?", f"?geo_ids[]={geo_id}&", 1)
        return base

    today = [_build_token_url(key, now_local_ref) for key in sensor_keys]
    tomorrow = [_build_token_url(key, next_day_local_ref) for key in sensor_keys]
    return today, tomorrow
