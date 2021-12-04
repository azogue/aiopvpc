"""
Simple aio library to download Spanish electricity hourly prices.

* URL for JSON daily files
* Parser for the contents of the JSON files
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Union

from aiopvpc.const import PRICE_PRECISION, REFERENCE_TZ, UTC_TZ, zoneinfo


def extract_pvpc_data(
    data: Dict[str, Any], key: str, tz: zoneinfo.ZoneInfo = REFERENCE_TZ
) -> Union[Dict[datetime, float], Dict[datetime, Dict[str, float]]]:
    """Parse the contents of a daily PVPC json file."""
    ts_init = datetime(
        *datetime.strptime(data["PVPC"][0]["Dia"], "%d/%m/%Y").timetuple()[:3],
        tzinfo=tz,
    ).astimezone(UTC_TZ)

    def _parse_tariff_val(value, prec=PRICE_PRECISION) -> float:
        return round(float(value.replace(",", ".")) / 1000.0, prec)

    return {
        ts_init + timedelta(hours=i): _parse_tariff_val(values_hour[key])
        for i, values_hour in enumerate(data["PVPC"])
    }
