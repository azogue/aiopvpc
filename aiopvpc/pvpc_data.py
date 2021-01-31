"""
Simple aio library to download Spanish electricity hourly prices.

Externalization of download and parsing logic for the `pvpc_hourly_pricing`
HomeAssistant integration,
https://www.home-assistant.io/integrations/pvpc_hourly_pricing/
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from time import monotonic
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import async_timeout
import pytz
from pytz.tzinfo import DstTzInfo

from .pvpc_download import (
    DEFAULT_TIMEOUT,
    extract_pvpc_data,
    get_url_for_daily_json,
    REFERENCE_TZ,
    TARIFF_KEYS,
)

_ATTRIBUTION = "Data retrieved from api.esios.ree.es by REE"


class PVPCData:
    """
    Data handler for PVPC hourly prices.

    * Async download of prices for each day
    * Generate state attributes for HA integration.
    * Async download of prices for a range of days

    - Prices are returned in a `Dict[datetime, float]`,
    with timestamps in local time and prices in €/kWh.

    - Without a specific `tariff`, it would return the entire collection
    of PVPC data, without any unit conversion,
    and type `Dict[datetime, Dict[str, float]`.
    """

    def __init__(
        self,
        tariff: Optional[str] = None,
        websession: Optional[aiohttp.ClientSession] = None,
        local_timezone: DstTzInfo = REFERENCE_TZ,
        logger: Optional[logging.Logger] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.source_available = True
        self.state: Optional[float] = None
        self.state_available = False
        self.attributes: Dict[str, Any] = {}

        self.tariff = tariff
        self.timeout = timeout

        self._session = websession
        self._with_initial_session = websession is not None
        self._local_timezone = local_timezone
        self._logger = logger or logging.getLogger(__name__)

        self._current_prices: Dict[datetime, float] = {}

        if tariff is None or tariff not in TARIFF_KEYS:
            self._logger.warning("Collecting detailed PVPC data for all tariffs")

    async def _download_pvpc_prices(self, day: date) -> Dict[datetime, Any]:
        """
        PVPC data extractor.

        Make GET request to 'api.esios.ree.es' and extract hourly prices for
        the selected tariff from the JSON daily file download
        of the official _Spain Electric Network_ (Red Eléctrica Española, REE)
        for the _Voluntary Price for Small Consumers_
        (Precio Voluntario para el Pequeño Consumidor, PVPC).

        Prices are referenced with tz-aware local datetimes.
        """
        url = get_url_for_daily_json(day)
        assert self._session is not None
        tariff = TARIFF_KEYS.get(self.tariff) if self.tariff else None
        try:
            with async_timeout.timeout(self.timeout):
                resp = await self._session.get(url)
                if resp.status < 400:
                    data = await resp.json()
                    return extract_pvpc_data(data, tariff, self._local_timezone)
        except KeyError:
            self._logger.debug("Bad try on getting prices for %s", day)
        except asyncio.TimeoutError:
            if self.source_available:
                self._logger.warning("Timeout error requesting data from '%s'", url)
        except aiohttp.ClientError:
            if self.source_available:
                self._logger.warning("Client error in '%s'", url)
        return {}

    async def async_update_prices(self, now: datetime) -> Dict[datetime, float]:
        """Update electricity prices from the ESIOS API."""
        utc_now = now.astimezone(pytz.UTC)
        localized_now = utc_now.astimezone(self._local_timezone)
        prices = await self._download_pvpc_prices(localized_now.date())
        if not prices:
            return prices

        # At evening, it is possible to retrieve next day prices
        if utc_now.hour >= 18:
            next_day = (utc_now + timedelta(days=1)).date()
            prices_fut = await self._download_pvpc_prices(next_day)
            if prices_fut:
                prices.update(prices_fut)

        self._current_prices.update(prices)
        self._logger.debug(
            "Download done, now with %d prices from %s Local Time",
            len(self._current_prices),
            list(self._current_prices)[0].strftime("%Y-%m-%d %Hh"),
        )

        return prices

    def process_state_and_attributes(self, utc_now: datetime) -> bool:
        """
        Generate the current state and sensor attributes.

        The data source provides prices in 0 to 24h sets.
        They are stored as tz-aware local datetimes.
        """
        attributes: Dict[str, Any] = {
            "attribution": _ATTRIBUTION,
            "tariff": self.tariff,
        }
        actual_time = (
            utc_now.astimezone(pytz.UTC)
            .replace(minute=0, second=0, microsecond=0)
            .astimezone(self._local_timezone)
        )
        if len(self._current_prices) > 25 and actual_time.hour < 20:
            # there are 'today' and 'next day' prices, but 'today' has expired
            max_age = actual_time.replace(hour=0)
            self._current_prices = {
                key_ts: price
                for key_ts, price in self._current_prices.items()
                if key_ts >= max_age
            }

        # set current price
        try:
            self.state = self._current_prices[actual_time]
            self.state_available = True
        except KeyError:
            self.state_available = False
            self.attributes = attributes
            return False

        # generate sensor attributes
        prices_sorted = dict(sorted(self._current_prices.items(), key=lambda x: x[1]))
        attributes["min_price"] = min(self._current_prices.values())
        attributes["min_price_at"] = next(iter(prices_sorted)).hour
        attributes["next_best_at"] = list(
            map(
                lambda x: x.hour,
                filter(lambda x: x >= actual_time, prices_sorted.keys()),
            )
        )

        def _is_tomorrow_price(ts, ref):
            return any(
                map(lambda x: x[0] > x[1], zip(ts.isocalendar(), ref.isocalendar()))
            )

        for ts_local, price_h in self._current_prices.items():
            if _is_tomorrow_price(ts_local, actual_time):
                attr_key = f"price_next_day_{ts_local.hour:02d}h"
            else:
                attr_key = f"price_{ts_local.hour:02d}h"
            if attr_key in attributes:  # DST change with duplicated hour :)
                attr_key += "_d"
            attributes[attr_key] = price_h

        self.attributes = attributes
        return True

    async def _download_worker(self, wk_name: str, queue: asyncio.Queue):
        downloaded_prices = []
        try:
            while True:
                day: date = await queue.get()
                tic = monotonic()
                prices = await self._download_pvpc_prices(day)
                took = monotonic() - tic
                queue.task_done()
                if not prices:
                    self._logger.warning(
                        "[%s]: Bad download for day: %s in %.3f s", wk_name, day, took
                    )
                    continue

                downloaded_prices.append((day, prices))
                self._logger.debug(
                    "[%s]: Task done for day: %s in %.3f s", wk_name, day, took
                )
        except asyncio.CancelledError:
            return downloaded_prices

    async def _multi_download(
        self, days_to_download: List[date], max_calls: int
    ) -> List[Tuple[date, Dict[datetime, Any]]]:
        """Multiple requests using an asyncio.Queue for concurrency."""
        queue: asyncio.Queue = asyncio.Queue()
        # setup `max_calls` queue workers
        worker_tasks = [
            asyncio.create_task(self._download_worker(f"worker-{i+1}", queue))
            for i in range(max_calls)
        ]
        # fill queue
        for day in days_to_download:
            queue.put_nowait(day)

        # wait for the queue to process all
        await queue.join()

        for task in worker_tasks:
            task.cancel()
        # Wait until all worker tasks are cancelled.
        wk_tasks_results = await asyncio.gather(*worker_tasks, return_exceptions=True)

        return sorted(
            (day_data for wk_results in wk_tasks_results for day_data in wk_results),
            key=lambda x: x[0],
        )

    async def _ensure_session(self):
        if self._session is None:
            assert not self._with_initial_session
            self._session = aiohttp.ClientSession()

    async def _close_temporal_session(self):
        if not self._with_initial_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def async_download_prices_for_range(
        self, start: datetime, end: datetime, concurrency_calls: int = 20
    ) -> Dict[datetime, Any]:
        """Download a time range burst of electricity prices from the ESIOS API."""

        def _adjust_local_timezone(ts: datetime) -> datetime:
            # adjust dates and tz from inputs
            if ts.tzinfo is None:
                return self._local_timezone.localize(ts)
            else:
                return ts.astimezone(self._local_timezone)

        start_tz_loc = _adjust_local_timezone(start)
        end_tz_loc = _adjust_local_timezone(end)
        delta: timedelta = end_tz_loc.date() - start_tz_loc.date()
        days_to_download = [
            start_tz_loc.date() + timedelta(days=i) for i in range(delta.days + 1)
        ]

        tic = monotonic()
        await self._ensure_session()
        data_days = await self._multi_download(days_to_download, concurrency_calls)
        await self._close_temporal_session()

        prices = {
            hour: hourly_data[hour]
            for (day, hourly_data) in data_days
            for hour in hourly_data
            if start_tz_loc <= hour <= end_tz_loc
        }
        if prices:
            self._logger.warning(
                "Download of %d prices from %s to %s in %.2f sec",
                len(prices),
                min(prices),
                max(prices),
                monotonic() - tic,
            )
        else:
            self._logger.error(
                "BAD Download of PVPC prices from %s to %s in %.2f sec",
                start,
                end,
                monotonic() - tic,
            )

        return prices

    def download_prices_for_range(
        self, start: datetime, end: datetime, concurrency_calls: int = 20
    ) -> Dict[datetime, Any]:
        """Blocking method to download a time range burst of elec prices."""
        return asyncio.run(
            self.async_download_prices_for_range(start, end, concurrency_calls)
        )
