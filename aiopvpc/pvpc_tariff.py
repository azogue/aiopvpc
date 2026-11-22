"""ESIOS API handler for HomeAssistant. PVPC tariff periods."""

from __future__ import annotations

from datetime import date, datetime, timedelta

_HOURS_P2 = (8, 9, 14, 15, 16, 17, 22, 23)
_HOURS_P2_CYM = (8, 9, 10, 15, 16, 17, 18, 23)

# CNMC Circular 3/2020 (Art. 7.3): 24h P3 valley period applies on weekends
# and fixed-date non-substitutable Spanish national holidays (+ Jan 6).
# Movable holidays (e.g. Good Friday) and substituted regional dates are excluded.
_NATIONAL_FIXED_HOLIDAYS_P3: frozenset[tuple[int, int]] = frozenset(
    {
        (1, 1),  # Año Nuevo
        (1, 6),  # Epifanía del Señor
        (5, 1),  # Fiesta del Trabajo
        (8, 15),  # Asunción de la Virgen
        (10, 12),  # Fiesta Nacional de España
        (11, 1),  # Todos los Santos
        (12, 6),  # Día de la Constitución Española
        (12, 8),  # La Inmaculada Concepción
        (12, 25),  # Natividad del Señor
    }
)


def is_national_p3_holiday(day: date) -> bool:
    """Return True if day is a fixed-date national holiday with 24h P3 period."""
    return (day.month, day.day) in _NATIONAL_FIXED_HOLIDAYS_P3


def _tariff_period_key(local_ts: datetime, zone_ceuta_melilla: bool) -> str:
    """Return period key (P1/P2/P3) for current hour."""
    day = local_ts.date()
    if day.isoweekday() >= 6 or local_ts.hour < 8 or is_national_p3_holiday(day):
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
