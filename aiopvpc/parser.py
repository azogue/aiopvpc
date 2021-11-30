"""
Simple aio library to download Spanish electricity hourly prices.

* URL for JSON daily files
* Parser for the contents of the JSON files
"""
from datetime import datetime, timedelta
from itertools import groupby
from operator import itemgetter
from typing import Any, Dict, Optional, Union

from aiopvpc.const import (
    ESIOS_INDICATOR_CO2_FREE_PERC,
    ESIOS_INDICATOR_CO2_GEN,
    EsiosIndicatorData,
    GEOZONE_ID2NAME,
    is_hourly_price,
    PRICE_PRECISION,
    REFERENCE_TZ,
    UTC_TZ,
    zoneinfo,
)


def extract_pvpc_data(
    data: Dict[str, Any],
    key: Optional[str] = None,
    tz: zoneinfo.ZoneInfo = REFERENCE_TZ,
) -> Union[Dict[datetime, float], Dict[datetime, Dict[str, float]]]:
    """Parse the contents of a daily PVPC json file."""
    ts_init = datetime(
        *datetime.strptime(data["PVPC"][0]["Dia"], "%d/%m/%Y").timetuple()[:3],
        tzinfo=tz,
    ).astimezone(UTC_TZ)

    def _parse_tariff_val(value, prec=PRICE_PRECISION) -> float:
        return round(float(value.replace(",", ".")) / 1000.0, prec)

    def _parse_val(value) -> float:
        return float(value.replace(",", "."))

    if key is not None:
        return {
            ts_init + timedelta(hours=i): _parse_tariff_val(values_hour[key])
            for i, values_hour in enumerate(data["PVPC"])
        }

    return {
        ts_init
        + timedelta(hours=i): {
            k: _parse_val(v) for k, v in values_hour.items() if k not in ("Dia", "Hora")
        }
        for i, values_hour in enumerate(data["PVPC"])
    }


def extract_indicator_data(data: Dict[str, Any]) -> EsiosIndicatorData:
    """Parse the contents of a historical indicator series json file."""
    indicator_data = data.pop("indicator")
    unit = "•".join(mag["name"] for mag in indicator_data["magnitud"])
    unit_tiempo = "•".join(mag["name"] for mag in indicator_data["tiempo"])
    unit += f"/{unit_tiempo}"
    if len(indicator_data["geos"]) == 1:
        geo_name = indicator_data["geos"][0]["geo_name"]
        unit += f" ({geo_name})"

    def _parse_dt(ts: str) -> datetime:
        return datetime.fromisoformat(ts).astimezone(UTC_TZ)

    def _value_unit_conversion(value: float) -> float:
        if is_hourly_price(indicator_data["id"]):
            # from €/MWh to €/kWh
            return round(float(value) / 1000.0, 5)
        elif indicator_data["id"] == ESIOS_INDICATOR_CO2_FREE_PERC:
            return round(float(value), 2)
        elif indicator_data["id"] == ESIOS_INDICATOR_CO2_GEN:
            # from tonCO2eq/MW to gCO2eq/kWh
            return round(1000.0 * float(value), 2)
        return value

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
    return EsiosIndicatorData(
        indicator=indicator_data["id"],
        name=indicator_data["name"],
        short_name=indicator_data["short_name"],
        unit=unit,
        data=parsed_data,
    )
