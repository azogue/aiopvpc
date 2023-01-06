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
    ATTRIBUTIONS,
    DataSource,
    DEFAULT_POWER_KW,
    DEFAULT_TIMEOUT,
    ESIOS_PVPC,
    EsiosApiData,
    PricesResponse,
    REFERENCE_TZ,
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
        esios_indicators: tuple[str, ...] = (ESIOS_PVPC,),
    ) -> None:
        """Set up API access."""
        self.states: dict[str, float | None] = {}
        self.sensor_attributes: dict[str, dict[str, Any]] = {}
        self.esios_indicators: set[str] = set(esios_indicators)

        self.timeout = timeout
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

    def _request_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Host": "api.esios.ree.es",
            "User-Agent": self._user_agents[0],
        }
        if self._data_source == "esios":
            assert self._api_token is not None
            headers["x-api-key"] = self._api_token
            headers["Authorization"] = f"Token token={self._api_token}"
        return headers

    async def _api_get_data(self, url: str) -> PricesResponse | None:
        assert self._session is not None
        resp = await self._session.get(url, headers=self._request_headers())
        if resp.status < 400:
            data = await resp.json()
            return extract_esios_data(data, url, self.tariff, tz=self._local_timezone)
        elif resp.status == 401 and self._data_source == "esios":
            _LOGGER.error("Unauthorized error with '%s': %s", self._data_source, url)
            self._data_source = "esios_public"
            # TODO raise for ConfigEntryAuthFailed
        elif resp.status == 403:  # pragma: no cover
            _LOGGER.warning("Forbidden error with '%s': %s", self._data_source, url)
            # loop user-agent and data-source
            self._user_agents.rotate()
        else:
            _LOGGER.error(
                "Unknown error [%d] with '%s': %s", resp.status, self._data_source, url
            )
        return None

    async def _download_daily_data(self, url: str) -> PricesResponse | None:
        """
        PVPC data extractor.

        Make GET request to 'api.esios.ree.es' and extract hourly prices for
        the selected tariff from the JSON daily file download
        of the official _Spain Electric Network_ (Red Eléctrica Española, REE)
        for the _Voluntary Price for Small Consumers_
        (Precio Voluntario para el Pequeño Consumidor, PVPC).

        Prices are referenced with datetimes in UTC.
        """
        try:
            async with async_timeout.timeout(2 * self.timeout):
                return await self._api_get_data(url)
        except KeyError as exc:
            _LOGGER.debug("Bad try on getting prices for %s ---> %s", url, exc)
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout error requesting data from '%s'", url)
        except aiohttp.ClientError as exc:
            _LOGGER.warning("Client error in '%s' -> %s", url, exc)
        return None

    async def async_update_all(
        self, current_data: EsiosApiData | None, now: datetime
    ) -> EsiosApiData:
        """
        Update all electricity prices from the ESIOS API.

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
                available=False,
                data_source=self._data_source,
                last_update=utc_now,
            )

        urls_now, urls_next = get_daily_urls_to_download(
            self._data_source,
            self.esios_indicators,
            local_ref_now,
            next_day,
        )
        updated = False
        tasks = []
        for url_now, url_next, data_id in zip(
            urls_now, urls_next, self.esios_indicators
        ):
            if data_id not in current_data["sensors"]:
                current_data["sensors"][data_id] = {}

            tasks.append(
                self._update_prices_series(
                    data_id,
                    current_data["sensors"][data_id],
                    url_now,
                    url_next,
                    local_ref_now,
                )
            )

        results = await asyncio.gather(*tasks)
        for new_data, data_id in zip(results, self.esios_indicators):
            if new_data:
                updated = True
                current_data["sensors"][data_id] = new_data

        if updated:
            current_data["available"] = True
            current_data["data_source"] = self._data_source
            current_data["last_update"] = utc_now

        for data_id in current_data["sensors"]:
            self.process_state_and_attributes(current_data, data_id, now)
        return current_data

    async def _update_prices_series(
        self,
        data_id: str,
        current_prices: dict[datetime, float],
        url_now: str,
        url_next: str,
        local_ref_now: datetime,
    ) -> dict[datetime, float] | None:
        current_num_prices = len(current_prices)
        if local_ref_now.hour >= 20 and current_num_prices > 30:
            # already have today+tomorrow prices, avoid requests
            _LOGGER.debug(
                "Evening download avoided, now with %d prices from %s UTC",
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
                "Download avoided, now with %d prices up to %s UTC",
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
                "Avoided: %s, with %d prices -> last: %s, download-day: %s",
                local_ref_now,
                current_num_prices,
                list(current_prices)[0].astimezone(REFERENCE_TZ).date(),
                local_ref_now.date(),
            )
        else:
            # make API call to download today prices
            prices_response = await self._download_daily_data(url_now)
            if prices_response is None or not prices_response["series"].get(data_id):
                return current_prices
            prices = prices_response["series"][data_id]
            current_prices.update(prices)

        # At evening, it is possible to retrieve next day prices
        if local_ref_now.hour >= 20:
            prices_fut_response = await self._download_daily_data(url_next)
            if prices_fut_response:
                prices_fut = prices_fut_response["series"][data_id]
                current_prices.update(prices_fut)

        _LOGGER.debug(
            "Download done, now with %d prices from %s UTC",
            len(current_prices),
            list(current_prices)[0].strftime("%Y-%m-%d %Hh"),
        )

        return current_prices

    @property
    def attribution(self) -> str:
        """Return data-source attribution string."""
        return ATTRIBUTIONS[self._data_source]

    def process_state_and_attributes(
        self, current_data: EsiosApiData, data_id: str, utc_now: datetime
    ) -> bool:
        """
        Generate the current state and sensor attributes.

        The data source provides prices in 0 to 24h sets, with correspondence
        with the main timezone in Spain. They are stored with UTC datetimes.

        Input `now: datetime` is assumed tz-aware in UTC.
        If not, it is converted to UTC from the original timezone,
        or set as UTC-time if it is a naive datetime.
        """
        attributes: dict[str, Any] = {"data_id": data_id}
        utc_time = ensure_utc_time(utc_now.replace(minute=0, second=0, microsecond=0))
        actual_time = utc_time.astimezone(self._local_timezone)
        current_prices = current_data["sensors"].get(data_id, {})
        if len(current_prices) > 25 and actual_time.hour < 20:
            # there are 'today' and 'next day' prices, but 'today' has expired
            max_age = (
                utc_time.astimezone(REFERENCE_TZ).replace(hour=0).astimezone(UTC_TZ)
            )
            current_data["sensors"][data_id] = {
                key_ts: price
                for key_ts, price in current_prices.items()
                if key_ts >= max_age
            }

        # set current price
        try:
            self.states[data_id] = current_data["sensors"][data_id][utc_time]
            current_data["available"] = True
        except KeyError:
            self.states[data_id] = None
            current_data["available"] = False
            self.sensor_attributes[data_id] = attributes
            return False

        # generate price attributes
        price_attrs = make_price_sensor_attributes(
            current_data["sensors"][data_id], utc_time, self._local_timezone
        )

        # generate PVPC 2.0TD sensor attributes
        if data_id == ESIOS_PVPC:
            local_time = utc_time.astimezone(self._local_timezone)
            (current_period, next_period, delta,) = get_current_and_next_tariff_periods(
                local_time, zone_ceuta_melilla=self.tariff != TARIFFS[0]
            )
            attributes["tariff"] = self.tariff
            attributes["period"] = current_period
            power = self._power_valley if current_period == "P3" else self._power
            attributes["available_power"] = int(1000 * power)
            attributes["next_period"] = next_period
            attributes["hours_to_next_period"] = int(delta.total_seconds()) // 3600

        self.sensor_attributes[data_id] = {**attributes, **price_attrs}
        return True
