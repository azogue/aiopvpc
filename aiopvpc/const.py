"""Simple aio library to download Spanish electricity hourly prices. Constants."""

import zoneinfo
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

DATE_CHANGE_TO_20TD = date(2021, 6, 1)

# Tariffs as internal keys in esios API data
TARIFF_20TD_IDS = ["PCB", "CYM"]

# Tariff names used in HomeAssistant integration
TARIFFS = ["2.0TD", "2.0TD (Ceuta/Melilla)"]

TARIFF2ID = dict(zip(TARIFFS, TARIFF_20TD_IDS))

# Contracted power
DEFAULT_POWER_KW = 3.3

# Prices are given in 0 to 24h sets, adjusted to the main timezone in Spain
REFERENCE_TZ = zoneinfo.ZoneInfo("Europe/Madrid")
UTC_TZ = zoneinfo.ZoneInfo("UTC")

DEFAULT_TIMEOUT = 10
PRICE_PRECISION = 5

DataSource = Literal["esios_public", "esios"]
GEOZONES = ["Península", "Canarias", "Baleares", "Ceuta", "Melilla", "España"]
GEOZONE_ID2NAME: dict[int, str] = {
    3: "España",
    8741: "Península",
    8742: "Canarias",
    8743: "Baleares",
    8744: "Ceuta",
    8745: "Melilla",
}
URL_PUBLIC_PVPC_RESOURCE = (
    "https://api.esios.ree.es/archives/70/download_json"
    "?locale=es&date={day:%Y-%m-%d}"
)
URL_ESIOS_TOKEN_RESOURCE = (
    "https://api.esios.ree.es/indicators/{ind}"
    + "?start_date={day:%Y-%m-%d}T00:00&end_date={day:%Y-%m-%d}T23:59"
)
ATTRIBUTIONS: dict[DataSource, str] = {
    "esios_public": "Data retrieved from api.esios.ree.es by REE",
    "esios": "Data retrieved with API token from api.esios.ree.es by REE",
}

# api.esios.ree.es/indicators
ESIOS_PVPC = "1001"
ESIOS_INJECTION = "1739"
ESIOS_MAG = "1900"  # regargo GAS
ESIOS_OMIE = "10211"  # precio mayorista
ESIOS_MARKET_ADJUSTMENT = "2108"  # ajuste mercado Indexada VS PVPC

# unique ids for each series
KEY_PVPC = "PVPC"
KEY_INJECTION = "INJECTION"
KEY_MAG = "MAG"  # regargo GAS
KEY_OMIE = "OMIE"  # precio mayorista
KEY_ADJUSTMENT = "ADJUSTMENT"  # ajuste mercado
# composed sensors
KEY_INDEXED = "INDEXED"  # precio indexada (:= PVPC - ADJUSTMENT)

ALL_SENSORS = (KEY_PVPC, KEY_INJECTION, KEY_MAG, KEY_OMIE, KEY_ADJUSTMENT)
SENSOR_KEY_TO_DATAID = {
    KEY_PVPC: ESIOS_PVPC,
    KEY_INJECTION: ESIOS_INJECTION,
    KEY_MAG: ESIOS_MAG,
    KEY_OMIE: ESIOS_OMIE,
    KEY_ADJUSTMENT: ESIOS_MARKET_ADJUSTMENT,
}
SENSOR_KEY_TO_NAME = {
    KEY_PVPC: "PVPC T. 2.0TD",
    KEY_INJECTION: "Precio de la energía excedentaria",
    KEY_MAG: "2.0TD Excedente o déficit ajuste liquidación",
    KEY_OMIE: "Precio medio horario final suma",
    KEY_ADJUSTMENT: "Ajuste de mercado a plazo",
    KEY_INDEXED: "Precio tarifa Indexada",
}
# API indicator dependencies for each price sensor
SENSOR_KEY_TO_API_SERIES = {
    KEY_PVPC: [KEY_PVPC],
    KEY_INJECTION: [KEY_INJECTION],
    KEY_MAG: [KEY_MAG],
    KEY_OMIE: [KEY_OMIE],
    KEY_ADJUSTMENT: [KEY_ADJUSTMENT],
    KEY_INDEXED: [KEY_PVPC, KEY_ADJUSTMENT],
}


@dataclass
class EsiosResponse:
    """Data schema for parsed data coming from ESIOS API."""

    name: str
    data_id: str
    last_update: datetime
    unit: str
    series: dict[str, dict[datetime, float]]


@dataclass
class EsiosApiData:
    """Data schema to store multiple series from ESIOS API."""

    last_update: datetime
    data_source: str
    sensors: dict[str, dict[datetime, float]]
    availability: dict[str, bool]
