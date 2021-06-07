"""Simple aio library to download Spanish electricity hourly prices."""
from .pvpc_data import DEFAULT_POWER_KW, PVPCData, TARIFFS

__all__ = ("DEFAULT_POWER_KW", "PVPCData", "TARIFFS")
