"""Simple aio library to download Spanish electricity hourly prices."""

from importlib.metadata import PackageNotFoundError, version

from .const import DEFAULT_POWER_KW, EsiosApiData, GEOZONES, TARIFFS
from .ha_helpers import get_enabled_sensor_keys
from .pvpc_data import BadApiTokenAuthError, PVPCData

try:
    __version__ = version("aiopvpc")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = (
    "DEFAULT_POWER_KW",
    "GEOZONES",
    "TARIFFS",
    "BadApiTokenAuthError",
    "EsiosApiData",
    "PVPCData",
    "__version__",
    "get_enabled_sensor_keys",
)
