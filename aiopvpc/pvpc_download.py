"""
Simple aio library to download Spanish electricity hourly prices.

* URL for JSON daily files
* Parser for the contents of the JSON files
"""
import logging
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Union

if sys.version_info[:2] >= (3, 9):  # pragma: no cover
    import zoneinfo  # pylint: disable=import-error
else:  # pragma: no cover
    from backports import zoneinfo  # pylint: disable=import-error

# Tariffs as internal keys in esios API data
ESIOS_TARIFFS = ["GEN", "NOC", "VHC"]
ESIOS_TARIFFS_NEW = ["PCB", "CYM"]

# Tariffs used in HomeAssistant integration
TARIFFS = ["normal", "discrimination", "electric_car"]
TARIFF_KEYS = dict(zip(TARIFFS, ESIOS_TARIFFS))
TARIFFS_NEW = ["2.0TD", "2.0TD (Ceuta/Melilla)"]
TARIFF_KEYS_NEW = dict(zip(TARIFFS_NEW, ESIOS_TARIFFS_NEW))

# Prices are given in 0 to 24h sets, adjusted to the main timezone in Spain
REFERENCE_TZ = zoneinfo.ZoneInfo("Europe/Madrid")
UTC_TZ = zoneinfo.ZoneInfo("UTC")

DEFAULT_TIMEOUT = 5
DATE_CHANGE_TO_20TD = date(2021, 6, 1)
_PRECISION = 5
_RESOURCE = (
    "https://api.esios.ree.es/archives/70/download_json"
    "?locale=es&date={day:%Y-%m-%d}"
)


def get_url_for_daily_json(day: Union[date, datetime]) -> str:
    """Get URL for JSON file with PVPC data for a specific day (in Europe/Madrid TZ)."""
    return _RESOURCE.format(day=day)


def extract_pvpc_data(
    data: Dict[str, Any],
    key: Optional[str] = None,
    tz: zoneinfo.ZoneInfo = REFERENCE_TZ,
    zone_ceuta_melilla: bool = False,
) -> Union[Dict[datetime, float], Dict[datetime, Dict[str, float]]]:
    """Parse the contents of a daily PVPC json file."""
    ts_init = datetime(
        *datetime.strptime(data["PVPC"][0]["Dia"], "%d/%m/%Y").timetuple()[:3],
        tzinfo=tz,
    ).astimezone(UTC_TZ)

    if ts_init.date() >= date(2021, 6, 1) and key not in ESIOS_TARIFFS_NEW:
        logging.warning(
            "Bad call for prices with new 2.0TD tariff, "
            "'%s' is not valid anymore :(",
            key,
        )
        key = "CYM" if zone_ceuta_melilla else "PCB"

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
