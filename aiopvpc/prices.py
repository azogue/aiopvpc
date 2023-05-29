"""ESIOS API handler for HomeAssistant. Hourly price attributes."""
import zoneinfo
from datetime import datetime
from typing import Any

from .const import KEY_INJECTION


def _is_tomorrow_price(ts: datetime, ref: datetime) -> bool:
    return any(map(lambda x: x[0] > x[1], zip(ts.isocalendar(), ref.isocalendar())))


def _split_today_tomorrow_prices(
    current_prices: dict[datetime, float],
    utc_time: datetime,
    timezone: zoneinfo.ZoneInfo,
) -> tuple[dict[datetime, float], dict[datetime, float]]:
    local_time = utc_time.astimezone(timezone)
    today, tomorrow = {}, {}
    for ts_utc, price_h in current_prices.items():
        ts_local = ts_utc.astimezone(timezone)
        if _is_tomorrow_price(ts_local, local_time):
            tomorrow[ts_utc] = price_h
        else:
            today[ts_utc] = price_h
    return today, tomorrow


def _make_price_tag_attributes(
    prices: dict[datetime, float], timezone: zoneinfo.ZoneInfo, tomorrow: bool
) -> dict[str, Any]:
    prefix = "price_next_day_" if tomorrow else "price_"
    attributes = {}
    for ts_utc, price_h in prices.items():
        ts_local = ts_utc.astimezone(timezone)
        attr_key = f"{prefix}{ts_local.hour:02d}h"
        if attr_key in attributes:  # DST change with duplicated hour :)
            attr_key += "_d"
        attributes[attr_key] = price_h
    return attributes


def _make_price_stats_attributes(
    sensor_key: str,
    current_price: float,
    current_prices: dict[datetime, float],
    utc_time: datetime,
    timezone: zoneinfo.ZoneInfo,
) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    sign_is_best = 1 if sensor_key != KEY_INJECTION else -1
    prices_sorted = dict(
        sorted(current_prices.items(), key=lambda x: sign_is_best * x[1])
    )
    better_prices_ahead = [
        (ts, price)
        for ts, price in current_prices.items()
        if ts > utc_time and price * sign_is_best < current_price * sign_is_best
    ]
    if better_prices_ahead:
        next_better_ts, next_better_price = better_prices_ahead[0]
        delta_better = next_better_ts - utc_time
        attributes["next_better_price"] = next_better_price
        attributes["hours_to_better_price"] = int(delta_better.total_seconds()) // 3600
        attributes["num_better_prices_ahead"] = len(better_prices_ahead)

    try:
        attributes["price_position"] = (
            list(prices_sorted.values()).index(current_price) + 1
        )
    except ValueError:
        pass

    max_price = max(current_prices.values())
    min_price = min(current_prices.values())
    try:
        attributes["price_ratio"] = round(
            (current_price - min_price) / (max_price - min_price), 2
        )
    except ZeroDivisionError:  # pragma: no cover
        pass
    attributes["max_price"] = max_price
    best_price_at = next(iter(prices_sorted)).astimezone(timezone).hour
    worst_price_at = next(iter(reversed(prices_sorted))).astimezone(timezone).hour
    attributes["max_price_at"] = worst_price_at if sign_is_best else best_price_at
    attributes["min_price"] = min_price
    attributes["min_price_at"] = best_price_at if sign_is_best else worst_price_at
    attributes["next_best_at"] = [
        ts.astimezone(timezone).hour for ts in prices_sorted.keys() if ts >= utc_time
    ]
    return attributes


def make_price_sensor_attributes(
    sensor_key: str,
    current_prices: dict[datetime, float],
    utc_time: datetime,
    timezone: zoneinfo.ZoneInfo,
) -> dict[str, Any]:
    """Generate sensor attributes for hourly prices variables."""
    current_price = current_prices[utc_time]
    today, tomorrow = _split_today_tomorrow_prices(current_prices, utc_time, timezone)
    price_attrs = _make_price_stats_attributes(
        sensor_key, current_price, today, utc_time, timezone
    )
    price_tags = _make_price_tag_attributes(today, timezone, False)
    if tomorrow:
        tomorrow_prices = {
            f"{key} (next day)": value
            for key, value in _make_price_stats_attributes(
                sensor_key, current_price, tomorrow, utc_time, timezone
            ).items()
        }
        tomorrow_price_tags = _make_price_tag_attributes(tomorrow, timezone, True)
        price_attrs = {**price_attrs, **tomorrow_prices}
        price_tags = {**price_tags, **tomorrow_price_tags}
    return {**price_attrs, **price_tags}
