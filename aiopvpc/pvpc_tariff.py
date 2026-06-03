"""ESIOS API handler for HomeAssistant. PVPC tariff periods."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import holidays

_LOGGER = logging.getLogger(__name__)


class _LazyHolidayDict:
    """
    Lazy-loaded dict of Spanish national holidays (lunes-viernes only).

    Rules applied:
    - Only national holidays (ES, no subdivision/region).
    - Weekends excluded: already treated as P3 by isoweekday logic.
    - 'Observed' (trasladados) excluded: a working Monday should NOT become
      P3 just because the original holiday fell on a Sunday.
      The PVPC tariff uses the canonical holiday date, not the substitution.

    The cache is pre-warmed at module import time for the current year to
    force ``importlib.import_module('holidays.countries.spain')`` to happen
    synchronously.  Otherwise the holidays library's internal lazy import
    fires inside ``asyncio`` event loop and Home Assistant flags it as a
    blocking call.
    """

    def __init__(self) -> None:
        self._cache: dict[int, dict[date, str]] = {}

    def __getitem__(self, year: int) -> dict[date, str]:
        if year not in self._cache:
            try:
                raw = holidays.ES(years=year, observed=False, subdiv=None)
                self._cache[year] = {
                    d: name for d, name in raw.items() if d.isoweekday() <= 5
                }
            except _holiday_errors():
                self._cache[year] = {}
        return self._cache[year]

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, date):
            return False
        return key in self[key.year]


def _holiday_errors() -> tuple[type[BaseException], ...]:
    holiday_lib_error = getattr(holidays.utils, "HolidayLibError", None)
    if isinstance(holiday_lib_error, type) and issubclass(
        holiday_lib_error, BaseException
    ):
        return holiday_lib_error, ValueError, NotImplementedError, ImportError
    return ValueError, NotImplementedError, ImportError


def _prewarm_holidays_cache(
    cache: _LazyHolidayDict,
) -> _LazyHolidayDict:
    """Force holidays library imports at module-load time (sync).

    The ``holidays`` library lazily imports country modules via
    ``importlib.import_module`` on first use.  That is a blocking I/O call
    which Home Assistant detects and reports when it happens inside the
    asyncio event loop.  By accessing the cache for the **current** year at
    import time we ensure the import resolves synchronously before any async
    operation runs.
    """
    try:
        cache[date.today().year]  # noqa: B018  (intentional side-effect)
        _LOGGER.debug("Holidays cache pre-warmed for %d", date.today().year)
    except Exception:  # pragma: no cover
        _LOGGER.warning("Could not pre-warm holiday cache", exc_info=True)
    return cache


_HOURS_P2 = (8, 9, 14, 15, 16, 17, 22, 23)
_HOURS_P2_CYM = (8, 9, 10, 15, 16, 17, 18, 23)
_NATIONAL_EXTRA_HOLIDAYS_FOR_P3_PERIOD = _prewarm_holidays_cache(_LazyHolidayDict())


def _tariff_period_key(local_ts: datetime, zone_ceuta_melilla: bool) -> str:
    """Return period key (P1/P2/P3) for current hour."""
    day = local_ts.date()
    national_holiday = day in _NATIONAL_EXTRA_HOLIDAYS_FOR_P3_PERIOD
    if national_holiday or day.isoweekday() >= 6 or local_ts.hour < 8:
        return "P3"
    if zone_ceuta_melilla and local_ts.hour in _HOURS_P2_CYM:
        return "P2"
    if not zone_ceuta_melilla and local_ts.hour in _HOURS_P2:
        return "P2"
    return "P1"


def get_current_and_next_tariff_periods(
    local_ts: datetime, zone_ceuta_melilla: bool
) -> tuple[str, str, timedelta]:
    """Get tariff periods for PVPC 2.0TD."""
    current_period = _tariff_period_key(local_ts, zone_ceuta_melilla)
    delta = timedelta(hours=1)
    while (
        next_period := _tariff_period_key(local_ts + delta, zone_ceuta_melilla)
    ) == current_period:
        delta += timedelta(hours=1)
    return current_period, next_period, delta
