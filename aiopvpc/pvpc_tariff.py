"""ESIOS API handler for HomeAssistant. PVPC tariff periods."""
from __future__ import annotations

from datetime import date, datetime, timedelta

_HOURS_P2 = (8, 9, 14, 15, 16, 17, 22, 23)
_HOURS_P2_CYM = (8, 9, 10, 15, 16, 17, 18, 23)
# TODO review 'festivos nacionales no sustituibles de fecha fija', + 6/1
# obtained from `holidays` library,
# - with weekend days disabled (already full P3)
# - no 'translated' holidays
# - no 'Jueves Santo' as special day
_NATIONAL_EXTRA_HOLIDAYS_FOR_P3_PERIOD = {
    2021: {
        date(2021, 1, 1): "(viernes), Año nuevo",
        date(2021, 1, 6): "(miércoles), Epifanía del Señor",
        # date(2021, 4, 1): "(jueves), Jueves Santo",
        date(2021, 4, 2): "(viernes), Viernes Santo",
        # date(2021, 5, 1): "(sábado), Día del Trabajador",
        # date(2021, 8, 15): "(domingo), Asunción de la Virgen",
        date(2021, 10, 12): "(martes), Día de la Hispanidad",
        date(2021, 11, 1): "(lunes), Todos los Santos",
        date(2021, 12, 6): "(lunes), Día de la Constitución Española",
        date(2021, 12, 8): "(miércoles), La Inmaculada Concepción",
        # date(2021, 12, 25): "(sábado), Navidad",
    },
    2022: {
        # date(2022, 1, 1): "(sábado), Año nuevo",
        date(2022, 1, 6): "(jueves), Epifanía del Señor",
        date(2022, 4, 15): "(viernes), Viernes Santo",
        date(2022, 8, 15): "(lunes), Asunción de la Virgen",
        date(2022, 10, 12): "(miércoles), Día de la Hispanidad",
        date(2022, 11, 1): "(martes), Todos los Santos",
        date(2022, 12, 6): "(martes), Día de la Constitución Española",
        date(2022, 12, 8): "(jueves), La Inmaculada Concepción",
        # date(2022, 12, 26): "(lunes), Navidad (Trasladado)",
    },
    2023: {
        # date(2023, 1, 1): "(domingo), Año nuevo",
        date(2023, 1, 6): "(viernes), Epifanía del Señor",
        # date(2023, 4, 6): "(jueves), Jueves Santo",
        date(2023, 4, 7): "(viernes), Viernes Santo",
        date(2023, 5, 1): "(lunes), Día del Trabajador",
        date(2023, 8, 15): "(martes), Asunción de la Virgen",
        date(2023, 10, 12): "(jueves), Día de la Hispanidad",
        date(2023, 11, 1): "(miércoles), Todos los Santos",
        date(2023, 12, 6): "(miércoles), Día de la Constitución Española",
        date(2023, 12, 8): "(viernes), La Inmaculada Concepción",
        date(2023, 12, 25): "(lunes), Navidad",
    },
    2024: {
        date(2024, 1, 1): "(lunes), Año nuevo",
        # date(2024, 1, 6): "(sábado), Epifanía del Señor",
        # date(2024, 3, 28): "(jueves), Jueves Santo",
        date(2024, 3, 29): "(viernes), Viernes Santo",
        date(2024, 5, 1): "(miércoles), Día del Trabajador",
        date(2024, 8, 15): "(jueves), Asunción de la Virgen",
        # date(2024, 10, 12): "(sábado), Día de la Hispanidad",
        date(2024, 11, 1): "(viernes), Todos los Santos",
        date(2024, 12, 6): "(viernes), Día de la Constitución Española",
        # date(2024, 12, 8): "(domingo), La Inmaculada Concepción",
        date(2024, 12, 25): "(miércoles), Navidad",
    },
    2025: {
        date(2025, 1, 1): "(miércoles), Año nuevo",
        date(2025, 1, 6): "(lunes), Epifanía del Señor",
        # date(2025, 4, 17): "(jueves), Jueves Santo",
        date(2025, 4, 18): "(viernes), Viernes Santo",
        date(2025, 5, 1): "(jueves), Día del Trabajador",
        date(2025, 8, 15): "(viernes), Asunción de la Virgen",
        # date(2025, 10, 12): "(domingo), Día de la Hispanidad",
        # date(2025, 11, 1): "(sábado), Todos los Santos",
        # date(2025, 12, 6): "(sábado), Día de la Constitución Española",
        date(2025, 12, 8): "(lunes), La Inmaculada Concepción",
        date(2025, 12, 25): "(jueves), Navidad",
    },
}


def _tariff_period_key(local_ts: datetime, zone_ceuta_melilla: bool) -> str:
    """Return period key (P1/P2/P3) for current hour."""
    day = local_ts.date()
    national_holiday = day in _NATIONAL_EXTRA_HOLIDAYS_FOR_P3_PERIOD[day.year]
    if national_holiday or day.isoweekday() >= 6 or local_ts.hour < 8:
        return "P3"
    elif zone_ceuta_melilla and local_ts.hour in _HOURS_P2_CYM:
        return "P2"
    elif not zone_ceuta_melilla and local_ts.hour in _HOURS_P2:
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
