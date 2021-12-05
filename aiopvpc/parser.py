"""
Simple aio library to download Spanish electricity hourly prices.

* URL for JSON daily files
* Parser for the contents of the JSON files
"""
from datetime import datetime, timedelta
from typing import Any, Dict, TypedDict

from aiopvpc.const import (
    DataSource,
    PRICE_PRECISION,
    REFERENCE_TZ,
    URL_APIDATOS_PRICES_RESOURCE,
    URL_PVPC_RESOURCE,
    UTC_TZ,
    zoneinfo,
)


class PricesResponse(TypedDict):
    """Data schema for parsed prices coming from `apidatos.ree.es`."""

    name: str
    data_id: str
    last_update: datetime
    unit: str
    series: Dict[str, Dict[datetime, float]]


def extract_prices_from_apidatos_ree(
    data: Dict[str, Any], tz: zoneinfo.ZoneInfo = REFERENCE_TZ
) -> PricesResponse:
    """Parse the contents of a query to 'precios-mercados-tiempo-real'."""
    ref_ts = datetime(2021, 1, 1, tzinfo=REFERENCE_TZ).astimezone(UTC_TZ)
    loc_ts = datetime(2021, 1, 1, tzinfo=tz).astimezone(UTC_TZ)
    loc_ts - ref_ts.astimezone(UTC_TZ)
    offset_timezone = loc_ts - ref_ts

    def _parse_dt(ts: str) -> datetime:
        return datetime.fromisoformat(ts).astimezone(UTC_TZ) + offset_timezone

    return PricesResponse(
        name=data["data"]["type"],
        data_id=data["data"]["id"],
        last_update=_parse_dt(data["data"]["attributes"]["last-update"]),
        unit="€/kWh",
        series={
            data_series["type"].replace(" (€/MWh)", ""): {
                _parse_dt(price["datetime"]): round(price["value"] / 1000.0, 5)
                for price in data_series["attributes"]["values"]
            }
            for data_series in data["included"]
        },
    )


def extract_prices_from_esios_public(
    data: Dict[str, Any], key: str, tz: zoneinfo.ZoneInfo = REFERENCE_TZ
) -> PricesResponse:
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

    return PricesResponse(
        name="PVPC ESIOS",
        data_id="legacy",
        last_update=datetime.utcnow().replace(microsecond=0, tzinfo=UTC_TZ),
        unit="€/kWh",
        series={"PVPC": pvpc_prices},
    )


def extract_pvpc_data(
    data: Dict[str, Any], url: str, key: str, tz: zoneinfo.ZoneInfo = REFERENCE_TZ
) -> Dict[datetime, float]:
    """Parse the contents of a daily PVPC json file."""
    if url.startswith("https://api.esios.ree.es/archives"):
        prices_data = extract_prices_from_esios_public(data, key, tz)
    elif url.startswith("https://apidatos.ree.es"):
        prices_data = extract_prices_from_apidatos_ree(data, tz)
    else:
        raise NotImplementedError(f"Data source not known: {url} >{data}")
    return prices_data["series"]["PVPC"]


def get_url_prices(
    source: DataSource, zone_ceuta_melilla: bool, now_local_ref: datetime
) -> str:
    """Make URL for PVPC prices."""
    if source == "esios_public":
        return URL_PVPC_RESOURCE.format(day=now_local_ref.date())

    start = now_local_ref.replace(hour=0, minute=0)
    end = now_local_ref.replace(hour=23, minute=59)
    return URL_APIDATOS_PRICES_RESOURCE.format(
        start=start, end=end, geo_id=8744 if zone_ceuta_melilla else 8741
    )
