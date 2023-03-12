"""
Simple aio library to download Spanish electricity hourly prices.

Externalization of download and parsing logic for the `pvpc_hourly_pricing`
HomeAssistant integration,
https://www.home-assistant.io/integrations/pvpc_hourly_pricing/
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from random import random
from typing import Any

import aiohttp
import async_timeout

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
    SENSOR_KEY_TO_DATAID,
    TARIFFS,
    UTC_TZ,
    zoneinfo,
)
from aiopvpc.parser import extract_esios_data, get_daily_urls_to_download
from aiopvpc.prices import make_price_sensor_attributes
from aiopvpc.pvpc_tariff import get_current_and_next_tariff_periods
from aiopvpc.utils import ensure_utc_time

_LOGGER = logging.getLogger(__name__)

# TODO REMOVE THIS USER-AGENT LOGIC
# 🙈😱 Use randomized standard User-Agent info to avoid server banning 😖🤷
_STANDARD_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) "
        "Gecko/20100101 Firefox/47.3"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X x.y; rv:42.0) "
        "Gecko/20100101 Firefox/43.4"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 11_3_1 like Mac OS X) "
        "AppleWebKit/603.1.30 (KHTML, like Gecko)"
    ),
    "Version/10.0 Mobile/14E304 Safari/602.1",
]


class BadApiTokenAuthError(Exception):
    """Exception to signal HA that ESIOS API token is invalid (401 status)."""

    pass  # noqa PIE790


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
        assert (data_source != "esios") or self._api_token is not None, data_source
        self._user_agents = deque(sorted(_STANDARD_USER_AGENTS, key=lambda x: random()))

        self._local_timezone = zoneinfo.ZoneInfo(str(local_timezone))
        assert tariff in TARIFFS
        self.tariff = tariff

        self._power = power
        self._power_valley = power_valley

    @property
    def using_private_api(self) -> bool:
        """Check if an API token is available and data-source is ESIOS."""
        return self._api_token is not None and self._data_source == "esios"

    async def _api_get_data(self, sensor_key: str, url: str) -> EsiosResponse | None:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Host": "api.esios.ree.es",
            "User-Agent": self._user_agents[0],
        }
        if self.using_private_api:
            assert self._api_token is not None
            headers["x-api-key"] = self._api_token
            headers["Authorization"] = f"Token token={self._api_token}"

        assert self._session is not None
        resp = await self._session.get(url, headers=headers)
        if resp.status < 400:
            data = await resp.json()
            return extract_esios_data(
                data, url, sensor_key, self.tariff, tz=self._local_timezone
            )
        elif resp.status in (401, 403) and self._data_source == "esios":
            _LOGGER.warning(
                "[%s] Unauthorized error with '%s': %s",
                sensor_key,
                self._data_source,
                url,
            )
            raise BadApiTokenAuthError(
                f"[{sensor_key}] Unauthorized access with API token '{self._api_token}'"
            )
        elif resp.status == 403:  # pragma: no cover
            _LOGGER.warning(
                "[%s] Forbidden error with '%s': %s", sensor_key, self._data_source, url
            )
            # loop user-agent and data-source
            self._user_agents.rotate()
        else:
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
            async with async_timeout.timeout(self._timeout):
                return await self._api_get_data(sensor_key, url)
        except (AttributeError, KeyError) as exc:
            _LOGGER.debug("[%s] Bad try on getting prices (%s)", sensor_key, exc)
        except asyncio.TimeoutError:
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
        )
        try:
            prices = await self._download_daily_data(KEY_PVPC, today[0])
        except BadApiTokenAuthError:
            return False
        return prices is not None

    def update_active_sensors(self, data_id: str, enabled: bool):
        """Update enabled API indicators to download."""
        assert data_id in ALL_SENSORS
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

        urls_now, urls_next = get_daily_urls_to_download(
            self._data_source,
            self._sensor_keys,
            local_ref_now,
            next_day,
        )
        updated = False
        tasks = []
        for url_now, url_next, sensor_key in zip(
            urls_now, urls_next, self._sensor_keys
        ):
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
        for new_data, sensor_key in zip(results, self._sensor_keys):
            if new_data:
                updated = True
                current_data.sensors[sensor_key] = new_data
                current_data.availability[sensor_key] = True

        if updated:
            current_data.data_source = self._data_source
            current_data.last_update = utc_now

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
        if local_ref_now.hour >= 20 and current_num_prices > 30:
            # already have today+tomorrow prices, avoid requests
            _LOGGER.debug(
                "[%s] Evening download avoided, now with %d prices from %s UTC",
                sensor_key,
                current_num_prices,
                list(current_prices)[0].strftime("%Y-%m-%d %Hh"),
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
            list(current_prices)[0].astimezone(REFERENCE_TZ).date()
            == local_ref_now.date()
        ):
            # avoid download of today prices
            _LOGGER.debug(
                "[%s] Avoided: %s, with %d prices -> last: %s, download-day: %s",
                sensor_key,
                local_ref_now,
                current_num_prices,
                list(current_prices)[0].astimezone(REFERENCE_TZ).date(),
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
            list(current_prices)[0].strftime("%Y-%m-%d %Hh"),
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
            "data_id": SENSOR_KEY_TO_DATAID[sensor_key],
        }
        utc_time = ensure_utc_time(utc_now.replace(minute=0, second=0, microsecond=0))
        actual_time = utc_time.astimezone(self._local_timezone)
        current_prices = current_data.sensors.get(sensor_key, {})
        if len(current_prices) > 25 and actual_time.hour < 20:
            # there are 'today' and 'next day' prices, but 'today' has expired
            max_age = (
                utc_time.astimezone(REFERENCE_TZ).replace(hour=0).astimezone(UTC_TZ)
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
