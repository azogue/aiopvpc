"""
Simple aio library to download Spanish electricity hourly prices.

* URL for JSON daily files
* Parser for the contents of the JSON files
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Union

import pytz

# Tariffs as internal keys in esios API data
ESIOS_TARIFFS = ["GEN", "NOC", "VHC"]

# Tariffs used in HomeAssistant integration
TARIFFS = ["normal", "discrimination", "electric_car"]
TARIFF_KEYS = dict(zip(TARIFFS, ESIOS_TARIFFS))

# Prices are given in 0 to 24h sets, adjusted to the main timezone in Spain
REFERENCE_TZ = pytz.timezone("Europe/Madrid")

DEFAULT_TIMEOUT = 5
_PRECISION = 5
_RESOURCE = (
    "https://api.esios.ree.es/archives/70/download_json"
    "?locale=es&date={day:%Y-%m-%d}"
)


def get_url_for_daily_json(day: Union[date, datetime]) -> str:
    """Get URL for JSON file with PVPC data for a specific day (in Europe/Madrid TZ)."""
    return _RESOURCE.format(day=day)


def extract_pvpc_data(
    data: Dict[str, Any], key: Optional[str] = None
) -> Union[Dict[datetime, float], Dict[datetime, Dict[str, float]]]:
    """Parse the contents of a daily PVPC json file."""
    ts_init = REFERENCE_TZ.localize(
        datetime.strptime(data["PVPC"][0]["Dia"], "%d/%m/%Y"),
        is_dst=False,  # dst change is never at 00:00
    ).astimezone(pytz.UTC)

    def _parse_tariff_val(value, prec=_PRECISION) -> float:
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
