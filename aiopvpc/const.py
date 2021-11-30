"""
Simple aio library to download Spanish electricity hourly prices. Constants.
"""
import sys
from datetime import date, datetime, timedelta
from typing import Dict, TypedDict

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

# ESIOS Indicators constants, methods, and data-schemas
ESIOS_INDICATOR_PVPC = 1001
ESIOS_INDICATOR_INYECTION_PRICE = 1739
ESIOS_INDICATOR_CO2_GEN = 10355
ESIOS_INDICATOR_CO2_FREE_PERC = 10033

ESIOS_BASE_URL = "https://api.esios.ree.es"
ESIOS_HEADERS = {
    "Accept": "application/json; application/vnd.esios-api-v1+json",
    "Content-Type": "application/json",
    "Host": "api.esios.ree.es",
    # "User-Agent": "aioesios Python library",
}

HA_IMPLEMENTED_IDS = ["pvpc", "inyection_price", "co2_gen", "co2_free"]
_INDICATOR_IDS: Dict[str, int] = {
    "PVPC": ESIOS_INDICATOR_PVPC,
    "INYECTION": ESIOS_INDICATOR_INYECTION_PRICE,
    "CO2_GEN": ESIOS_INDICATOR_CO2_GEN,
    "CO2_FREE": ESIOS_INDICATOR_CO2_FREE_PERC,
}
ESIOS_IDS = list(_INDICATOR_IDS.keys())

GEOZONES = ["Península", "Canarias", "Baleares", "Ceuta", "Melilla"]
GEOZONE_ID2NAME: Dict[int, str] = {
    3: "España",
    8741: "Península",
    8742: "Canarias",
    8743: "Baleares",
    8744: "Ceuta",
    8745: "Melilla",
}
_INDICATOR_NAMES = {ind: name for name, ind in _INDICATOR_IDS.items()}
_INDICATOR_IS_PRICE: Dict[int, bool] = {
    ESIOS_INDICATOR_PVPC: True,
    ESIOS_INDICATOR_INYECTION_PRICE: True,
    ESIOS_INDICATOR_CO2_GEN: False,
    ESIOS_INDICATOR_CO2_FREE_PERC: False,
}
_INDICATOR_MIN_DELTA_UPDATE: Dict[int, timedelta] = {
    ESIOS_INDICATOR_PVPC: timedelta(minutes=30),
    ESIOS_INDICATOR_INYECTION_PRICE: timedelta(minutes=30),
    ESIOS_INDICATOR_CO2_GEN: timedelta(minutes=10),
    ESIOS_INDICATOR_CO2_FREE_PERC: timedelta(minutes=10),
}
INDICATOR_IS_GEOZONED: Dict[int, bool] = {
    ESIOS_INDICATOR_PVPC: True,
    ESIOS_INDICATOR_INYECTION_PRICE: False,
    ESIOS_INDICATOR_CO2_GEN: False,
    ESIOS_INDICATOR_CO2_FREE_PERC: False,
}


def is_hourly_price(indicator: int) -> bool:
    """Filter ESIOS variables referred to hourly prices."""
    return _INDICATOR_IS_PRICE[indicator]


def get_esios_id(key_indicator: str) -> int:
    """Get ESIOS indicator for sensor key."""
    return _INDICATOR_IDS[key_indicator]


def get_esios_key(indicator: int) -> str:
    """Get key name from ESIOS indicator."""
    return _INDICATOR_NAMES[indicator]


def get_delta_update(indicator: int) -> timedelta:
    """Get minimum timedelta to wait before fetching more data."""
    return _INDICATOR_MIN_DELTA_UPDATE[indicator]


class EsiosIndicatorData(TypedDict):
    """Container for used data from standardized ESIOS indicators."""

    indicator: int
    name: str
    short_name: str
    unit: str
    data: Dict[str, Dict[datetime, float]]
