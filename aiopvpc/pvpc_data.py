"""
Simple aio library to download Spanish electricity hourly prices.

Externalization of download and parsing logic for the `pvpc_hourly_pricing`
HomeAssistant integration,
https://www.home-assistant.io/integrations/pvpc_hourly_pricing/
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from aiopvpc.const import (
    ALL_SENSORS,
    ATTRIBUTIONS,
    DataSource,
    DEFAULT_POWER_KW,
    DEFAULT_TIMEOUT,
    EsiosApiData,
    EsiosResponse,
    KEY_PVPC,
    REFERENCE_TZ,
    SENSOR_KEY_TO_API_SERIES,
    SENSOR_KEY_TO_DATAID,
    TARIFFS,
    UTC_TZ,
    zoneinfo,
)
from aiopvpc.parser import (
    extract_esios_data,
    get_daily_urls_to_download,
    resolve_geo_zone,
)
from aiopvpc.prices import add_composed_price_sensors, make_price_sensor_attributes
from aiopvpc.pvpc_tariff import get_current_and_next_tariff_periods
from aiopvpc.utils import ensure_utc_time

_LOGGER = logging.getLogger(__name__)


class BadApiTokenAuthError(Exception):
    """Exception to signal HA that ESIOS API token is invalid (401 status)."""


class PVPCData:
    """
    Data handler for PVPC hourly prices.

    * Async download of prices for each day
    * Generate state attributes for HA integration.

    - Prices are returned in a `dict[datetime, float]`,
    with timestamps in UTC and prices in €/kWh.
    """

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        tariff: str = TARIFFS[0],
        local_timezone: str | zoneinfo.ZoneInfo = REFERENCE_TZ,
        power: float = DEFAULT_POWER_KW,
        power_valley: float = DEFAULT_POWER_KW,
        timeout: float = DEFAULT_TIMEOUT,
        data_source: DataSource = "esios_public",
        api_token: str | None = None,
        sensor_keys: tuple[str, ...] = (KEY_PVPC,),
        geo_zone: str | None = None,
    ) -> None:
        """Set up API access."""
        self.states: dict[str, float | None] = {}
        self.sensor_attributes: dict[str, dict[str, Any]] = {}
        self._sensor_keys: set[str] = {key for key in sensor_keys if key in ALL_SENSORS}

        self._timeout = timeout
        self._session = session
        self._data_source = data_source
        self._api_token = api_token
        if self._api_token is not None:
            self._data_source = "esios"
        if data_source == "esios" and self._api_token is None:
            raise ValueError("API token is required when data_source is 'esios'")

        self._local_timezone = zoneinfo.ZoneInfo(str(local_timezone))
        if tariff not in TARIFFS:
            raise ValueError(f"Unknown tariff '{tariff}'. Expected one of {TARIFFS}")
        self.tariff = tariff
        self._explicit_geo_zone = geo_zone
        self._geo_zone = resolve_geo_zone(tariff, self._local_timezone, geo_zone)

        self._power = power
        self._power_valley = power_valley

    @property
    def using_private_api(self) -> bool:
        """Check if an API token is available and data-source is ESIOS."""
        return self._api_token is not None and self._data_source == "esios"

    async def _api_get_data(self, sensor_key: str, url: str) -> EsiosResponse | None:
        headers = {
            "Accept": (
                "application/json; application/vnd.esios-api-v2+json"
                if self.using_private_api
                else "application/json"
            ),
            "Content-Type": "application/json",
            "Host": "api.esios.ree.es",
        }
        if self.using_private_api:
            assert self._api_token is not None
            headers["x-api-key"] = self._api_token
            headers["Authorization"] = f"Token token={self._api_token}"

        assert self._session is not None
        async with self._session.get(url, headers=headers) as resp:
            if resp.status < 400:
                data = await resp.json()
                return extract_esios_data(
                    data,
                    url,
                    sensor_key,
                    self.tariff,
                    tz=self._local_timezone,
                    geo_zone=self._geo_zone,
                )
            if resp.status in (401, 403) and self._data_source == "esios":
                _LOGGER.warning(
                    "[%s] Unauthorized error with '%s': %s",
                    sensor_key,
                    self._data_source,
                    url,
                )
                raise BadApiTokenAuthError(
                    f"[{sensor_key}] Unauthorized access with ESIOS API token"
                )
            if resp.status == 429:
                retry_after = resp.headers.get("Retry-After")
                _LOGGER.warning(
                    "[%s] Rate limited [429] with '%s' (Retry-After: %s): %s",
                    sensor_key,
                    self._data_source,
                    retry_after,
                    url,
                )
                return None
            _LOGGER.error(
                "[%s] Unknown error [%d] with '%s': %s",
                sensor_key,
                resp.status,
                self._data_source,
                url,
            )
            return None

    async def _download_daily_data(
        self, sensor_key: str, url: str
    ) -> EsiosResponse | None:
        """
        PVPC data extractor.

        Make GET request to 'api.esios.ree.es' and extract hourly prices.

        Prices are referenced with datetimes in UTC.
        """
        try:
            async with asyncio.timeout(self._timeout):
                return await self._api_get_data(sensor_key, url)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            _LOGGER.debug("[%s] Bad try on getting prices (%s)", sensor_key, exc)
        except TimeoutError:
            _LOGGER.warning(
                "[%s] Timeout error requesting data from '%s'", sensor_key, url
            )
        except aiohttp.ClientError as exc:
            _LOGGER.warning("[%s] Client error in '%s' -> %s", sensor_key, url, exc)
        except BadApiTokenAuthError:
            raise
        return None

    async def check_api_token(
        self, now: datetime, api_token: str | None = None
    ) -> bool:
        """Check if ESIOS API token is valid."""
        local_ref_now = ensure_utc_time(now).astimezone(REFERENCE_TZ)
        if api_token is not None:
            self._api_token = api_token
        self._data_source = "esios"
        today, _ = get_daily_urls_to_download(
            self._data_source,
            {KEY_PVPC},
            local_ref_now,
            local_ref_now,
            geo_zone=self._explicit_geo_zone,
        )
        try:
            prices = await self._download_daily_data(KEY_PVPC, today[0])
        except BadApiTokenAuthError:
            return False
        return prices is not None

    def update_active_sensors(self, data_id: str, enabled: bool) -> None:
        """Update enabled API indicators to download."""
        if data_id not in ALL_SENSORS:
            raise ValueError(
                f"Unknown sensor '{data_id}'. Expected one of {ALL_SENSORS}"
            )
        if enabled:
            self._sensor_keys.add(data_id)
        elif data_id in self._sensor_keys:
            self._sensor_keys.remove(data_id)

    async def async_update_all(
        self, current_data: EsiosApiData | None, now: datetime
    ) -> EsiosApiData:
        """
        Update all prices from the ESIOS API.

        Input `now: datetime` is assumed tz-aware in UTC.
        If not, it is converted to UTC from the original timezone,
        or set as UTC-time if it is a naive datetime.
        """
        utc_now = ensure_utc_time(now)
        local_ref_now = utc_now.astimezone(REFERENCE_TZ)
        next_day = local_ref_now + timedelta(days=1)

        if current_data is None:
            current_data = EsiosApiData(
                sensors={},
                availability={},
                data_source=self._data_source,
                last_update=utc_now,
            )

        api_sensors = {
            api_sensor_key
            for sensor_key in self._sensor_keys
            for api_sensor_key in SENSOR_KEY_TO_API_SERIES[sensor_key]
        }
        urls_now, urls_next = get_daily_urls_to_download(
            self._data_source,
            api_sensors,
            local_ref_now,
            next_day,
            geo_zone=self._explicit_geo_zone,
        )
        updated = False
        tasks = []
        for url_now, url_next, sensor_key in zip(urls_now, urls_next, api_sensors):
            if sensor_key not in current_data.sensors:
                current_data.sensors[sensor_key] = {}

            tasks.append(
                self._update_prices_series(
                    sensor_key,
                    current_data.sensors[sensor_key],
                    url_now,
                    url_next,
                    local_ref_now,
                )
            )

        results = await asyncio.gather(*tasks)
        for new_data, sensor_key in zip(results, api_sensors):
            if new_data:
                updated = True
                current_data.sensors[sensor_key] = new_data
                current_data.availability[sensor_key] = True

        if updated:
            current_data.data_source = self._data_source
            current_data.last_update = utc_now

        add_composed_price_sensors(current_data)
        for sensor_key in current_data.sensors:
            self.process_state_and_attributes(current_data, sensor_key, now)
        return current_data

    async def _update_prices_series(
        self,
        sensor_key: str,
        current_prices: dict[datetime, float],
        url_now: str,
        url_next: str,
        local_ref_now: datetime,
    ) -> dict[datetime, float] | None:
        current_num_prices = len(current_prices)
        last_local_date = (
            list(current_prices)[-1].astimezone(self._local_timezone).date()
            if current_prices
            else None
        )
        if (
            local_ref_now.hour >= 20
            and last_local_date is not None
            and last_local_date > local_ref_now.date()
        ):
            # already have today+tomorrow prices, avoid requests
            _LOGGER.debug(
                "[%s] Evening download avoided, now with %d prices from %s UTC",
                sensor_key,
                current_num_prices,
                next(iter(current_prices)).strftime("%Y-%m-%d %Hh"),
            )
            return None
        elif (
            local_ref_now.hour < 20
            and current_num_prices > 20
            and (
                list(current_prices)[-12].astimezone(REFERENCE_TZ).date()
                == local_ref_now.date()
            )
        ):
            # already have today prices, avoid request
            _LOGGER.debug(
                "[%s] Download avoided, now with %d prices up to %s UTC",
                sensor_key,
                current_num_prices,
                list(current_prices)[-1].strftime("%Y-%m-%d %Hh"),
            )
            return None

        if current_num_prices and (
            next(iter(current_prices)).astimezone(REFERENCE_TZ).date()
            == local_ref_now.date()
        ):
            # avoid download of today prices
            _LOGGER.debug(
                "[%s] Avoided: %s, with %d prices -> last: %s, download-day: %s",
                sensor_key,
                local_ref_now,
                current_num_prices,
                next(iter(current_prices)).astimezone(REFERENCE_TZ).date(),
                local_ref_now.date(),
            )
        else:
            # make API call to download today prices
            prices_response = await self._download_daily_data(sensor_key, url_now)
            if prices_response is None or not prices_response.series.get(sensor_key):
                return current_prices
            prices = prices_response.series[sensor_key]
            current_prices.update(prices)

        # At evening, it is possible to retrieve next day prices
        if local_ref_now.hour >= 20:
            prices_fut_response = await self._download_daily_data(sensor_key, url_next)
            if prices_fut_response:
                prices_fut = prices_fut_response.series[sensor_key]
                current_prices.update(prices_fut)

        _LOGGER.debug(
            "[%s] Download done, now with %d prices from %s UTC",
            sensor_key,
            len(current_prices),
            next(iter(current_prices)).strftime("%Y-%m-%d %Hh"),
        )

        return current_prices

    @property
    def attribution(self) -> str:
        """Return data-source attribution string."""
        return ATTRIBUTIONS[self._data_source]

    def process_state_and_attributes(
        self, current_data: EsiosApiData, sensor_key: str, utc_now: datetime
    ) -> bool:
        """
        Generate the current state and sensor attributes.

        The data source provides prices in 0 to 24h sets, with correspondence
        with the main timezone in Spain. They are stored with UTC datetimes.

        Input `now: datetime` is assumed tz-aware in UTC.
        If not, it is converted to UTC from the original timezone,
        or set as UTC-time if it is a naive datetime.
        """
        attributes: dict[str, Any] = {
            "sensor_id": sensor_key,
            "data_id": SENSOR_KEY_TO_DATAID.get(sensor_key, "composed"),
        }
        current_prices = current_data.sensors.get(sensor_key, {})
        slot_minute = (
            (utc_now.minute // 15) * 15
            if any(ts.minute != 0 for ts in current_prices)
            else 0
        )
        utc_time = ensure_utc_time(
            utc_now.replace(minute=slot_minute, second=0, microsecond=0)
        )
        actual_time = utc_time.astimezone(self._local_timezone)
        if len(current_prices) > 25 and actual_time.hour < 20:
            # there are 'today' and 'next day' prices, but 'today' has expired
            max_age = (
                utc_time.astimezone(REFERENCE_TZ)
                .replace(hour=0, minute=0)
                .astimezone(UTC_TZ)
            )
            current_data.sensors[sensor_key] = {
                key_ts: price
                for key_ts, price in current_prices.items()
                if key_ts >= max_age
            }

        # set current price
        try:
            self.states[sensor_key] = current_data.sensors[sensor_key][utc_time]
            current_data.availability[sensor_key] = True
        except KeyError:
            self.states[sensor_key] = None
            current_data.availability[sensor_key] = False
            self.sensor_attributes[sensor_key] = attributes
            return False

        # generate price attributes
        price_attrs = make_price_sensor_attributes(
            sensor_key, current_data.sensors[sensor_key], utc_time, self._local_timezone
        )

        # generate PVPC 2.0TD sensor attributes
        if sensor_key == KEY_PVPC:
            local_time = utc_time.astimezone(self._local_timezone)
            (
                current_period,
                next_period,
                delta,
            ) = get_current_and_next_tariff_periods(
                local_time, zone_ceuta_melilla=self.tariff != TARIFFS[0]
            )
            attributes["tariff"] = self.tariff
            attributes["period"] = current_period
            power = self._power_valley if current_period == "P3" else self._power
            attributes["available_power"] = int(1000 * power)
            attributes["next_period"] = next_period
            attributes["hours_to_next_period"] = int(delta.total_seconds()) // 3600

        self.sensor_attributes[sensor_key] = {**attributes, **price_attrs}
        return True
