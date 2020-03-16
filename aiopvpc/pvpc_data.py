"""
Simple aio library to download Spanish electricity hourly prices.

Externalization of download and parsing logic for the `pvpc_hourly_pricing`
HomeAssistant integration,
https://www.home-assistant.io/integrations/pvpc_hourly_pricing/
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Optional

import aiohttp
import async_timeout
import pytz

DEFAULT_TIMEOUT = 5
TARIFFS = ["normal", "discrimination", "electric_car"]

# Prices are given in 0 to 24h sets, adjusted to the main timezone in Spain
REFERENCE_TZ = pytz.timezone("Europe/Madrid")

_ATTRIBUTION = "Data retrieved from api.esios.ree.es by REE"
_PRECISION = 5
_RESOURCE = (
    "https://api.esios.ree.es/archives/70/download_json"
    "?locale=es&date={day:%Y-%m-%d}"
)
_TARIFF_KEYS = dict(zip(TARIFFS, ["GEN", "NOC", "VHC"]))


class PVPCData:
    """
    Data handler for PVPC hourly prices.

    * Async download of prices for each day
    * Generate state attributes for HA integration.
    """

    def __init__(
        self,
        tariff: str,
        websession: aiohttp.ClientSession,
        local_timezone: pytz.BaseTzInfo,
        logger: Optional[logging.Logger] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.source_available = True
        self.state = None
        self.state_available = False
        self.attributes = None

        self.tariff = tariff
        self.timeout = timeout

        self._local_timezone = local_timezone
        self._websession = websession
        self._logger = logger or logging.getLogger(__name__)

        self._current_prices: Dict[datetime, float] = {}

    async def _download_pvpc_prices(self, day: date) -> Dict[datetime, float]:
        """
        PVPC data extractor.

        Make GET request to 'api.esios.ree.es' and extract hourly prices for
        the selected tariff from the JSON daily file download
        of the official _Spain Electric Network_ (Red Eléctrica Española, REE)
        for the _Voluntary Price for Small Consumers_
        (Precio Voluntario para el Pequeño Consumidor, PVPC).

        Prices are referenced with datetimes in UTC.
        """
        url = _RESOURCE.format(day=day)
        key = _TARIFF_KEYS[self.tariff]
        try:
            with async_timeout.timeout(self.timeout):
                resp = await self._websession.get(url)
                if resp.status < 400:
                    data = await resp.json()
                    ts_init = (
                        datetime.strptime(data["PVPC"][0]["Dia"], "%d/%m/%Y")
                        .astimezone(REFERENCE_TZ)
                        .astimezone(pytz.UTC)
                    )
                    return {
                        ts_init
                        + timedelta(hours=i): round(
                            float(values_hour[key].replace(",", ".")) / 1000.0,
                            _PRECISION,
                        )
                        for i, values_hour in enumerate(data["PVPC"])
                    }
        except KeyError:
            self._logger.debug("Bad try on getting prices for %s", day)
        except asyncio.TimeoutError:
            if self.source_available:
                self._logger.warning(
                    "Timeout error requesting data from '%s'", url
                )
        except aiohttp.ClientError:
            if self.source_available:
                self._logger.warning("Client error in '%s'", url)
        return {}

    async def async_update_prices(self, now: datetime):
        """Update electricity prices from the ESIOS API."""
        localized_now = now.astimezone(pytz.UTC).astimezone(REFERENCE_TZ)
        prices = await self._download_pvpc_prices(localized_now.date())
        if not prices:
            return prices

        # At evening, it is possible to retrieve next day prices
        if localized_now.hour >= 20:
            next_day = (localized_now + timedelta(days=1)).date()
            prices_fut = await self._download_pvpc_prices(next_day)
            if prices_fut:
                prices.update(prices_fut)

        self._current_prices.update(prices)
        self._logger.debug(
            "Download done, now with %d prices from %s UTC",
            len(self._current_prices),
            list(self._current_prices)[0].strftime("%Y-%m-%d %Hh"),
        )

        return prices

    def process_state_and_attributes(self, utc_now: datetime) -> bool:
        """
        Generate the current state and sensor attributes.

        The data source provides prices in 0 to 24h sets, with correspondence
        with the main timezone in Spain. They are stored with UTC datetimes.
        """

        def _local(dt_utc: datetime) -> datetime:
            return dt_utc.astimezone(self._local_timezone)

        attributes = {"attribution": _ATTRIBUTION, "tariff": self.tariff}
        utc_time = utc_now.astimezone(pytz.UTC).replace(
            minute=0, second=0, microsecond=0
        )
        actual_time = _local(utc_time)
        if len(self._current_prices) > 25 and actual_time.hour < 20:
            # there are 'today' and 'next day' prices, but 'today' has expired
            max_age = (
                utc_time.astimezone(REFERENCE_TZ)
                .replace(hour=0)
                .astimezone(pytz.UTC)
            )
            self._current_prices = {
                key_ts: price
                for key_ts, price in self._current_prices.items()
                if key_ts >= max_age
            }

        # set current price
        try:
            self.state = self._current_prices[utc_time]
            self.state_available = True
        except KeyError:
            self.state_available = False
            self.attributes = attributes
            return False

        # generate sensor attributes
        prices_sorted = dict(
            sorted(self._current_prices.items(), key=lambda x: x[1])
        )
        attributes["min_price"] = min(self._current_prices.values())
        attributes["min_price_at"] = _local(next(iter(prices_sorted))).hour
        attributes["next_best_at"] = list(
            map(
                lambda x: _local(x).hour,
                filter(lambda x: x >= utc_time, prices_sorted.keys()),
            )
        )
        for ts_utc, price_h in self._current_prices.items():
            ts_local = _local(ts_utc)
            if ts_local.day > actual_time.day:
                attr_key = f"price_next_day_{ts_local.hour:02d}h"
            elif ts_local.day < actual_time.day:
                attr_key = f"price_last_day_{ts_local.hour:02d}h"
            else:
                attr_key = f"price_{ts_local.hour:02d}h"
            if attr_key in attributes:  # DST change with duplicated hour :)
                attr_key += "_d"
            attributes[attr_key] = price_h

        self.attributes = attributes
        return True
