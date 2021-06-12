"""
Simple aio library to download Spanish electricity hourly prices. Constants.
"""
import sys
from datetime import date

if sys.version_info[:2] >= (3, 9):  # pragma: no cover
    import zoneinfo  # pylint: disable=import-error
else:  # pragma: no cover
    from backports import zoneinfo  # type: ignore

DATE_CHANGE_TO_20TD = date(2021, 6, 1)

# Tariffs as internal keys in esios API data
TARIFF_20TD_IDS = ["PCB", "CYM"]
OLD_TARIFS_IDS = ["GEN", "NOC", "VHC"]

# Tariff names used in HomeAssistant integration
TARIFFS = ["2.0TD", "2.0TD (Ceuta/Melilla)"]
OLD_TARIFFS = ["normal", "discrimination", "electric_car"]

TARIFF2ID = dict(zip(TARIFFS, TARIFF_20TD_IDS))
OLD_TARIFF2ID = dict(zip(OLD_TARIFFS, OLD_TARIFS_IDS))

# Contracted power
DEFAULT_POWER_KW = 3.3

# Prices are given in 0 to 24h sets, adjusted to the main timezone in Spain
REFERENCE_TZ = zoneinfo.ZoneInfo("Europe/Madrid")
UTC_TZ = zoneinfo.ZoneInfo("UTC")

DEFAULT_TIMEOUT = 5
PRICE_PRECISION = 5
URL_PVPC_RESOURCE = (
    "https://api.esios.ree.es/archives/70/download_json"
    "?locale=es&date={day:%Y-%m-%d}"
)
ATTRIBUTION = "Data retrieved from api.esios.ree.es by REE"
