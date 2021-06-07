"""
Simple aio library to download Spanish electricity hourly prices.

* URL for JSON daily files
* Parser for the contents of the JSON files
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Union

from aiopvpc.const import (
    PRICE_PRECISION,
    REFERENCE_TZ,
    URL_PVPC_RESOURCE,
    UTC_TZ,
    zoneinfo,
)


def get_url_for_daily_json(day: Union[date, datetime]) -> str:
    """Get URL for JSON file with PVPC data for a specific day (in Europe/Madrid TZ)."""
    return URL_PVPC_RESOURCE.format(day=day)


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
