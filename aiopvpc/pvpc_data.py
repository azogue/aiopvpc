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
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import aiohttp
import async_timeout

from aiopvpc.pvpc_download import (
    DATE_CHANGE_TO_20TD,
    DEFAULT_TIMEOUT,
    extract_pvpc_data,
    get_url_for_daily_json,
    REFERENCE_TZ,
    TARIFF_KEYS,
    TARIFF_KEYS_NEW,
    TARIFFS_NEW,
    UTC_TZ,
    zoneinfo,
)

_ATTRIBUTION = "Data retrieved from api.esios.ree.es by REE"


def _ensure_utc_time(ts: datetime):
    if ts.tzinfo is None:
        return datetime(*ts.timetuple()[:6], tzinfo=UTC_TZ)
    elif str(ts.tzinfo) != str(UTC_TZ):
        return ts.astimezone(UTC_TZ)
    return ts


class PVPCData:
    """
    Data handler for PVPC hourly prices.

    * Async download of prices for each day
    * Generate state attributes for HA integration.
    * Async download of prices for a range of days

    - Prices are returned in a `Dict[datetime, float]`,
    with timestamps in UTC and prices in €/kWh.

    - Without a specific `tariff`, it would return the entire collection
    of PVPC data, without any unit conversion,
    and type `Dict[datetime, Dict[str, float]`.
    """

    def __init__(
        self,
        tariff: Optional[str] = None,
        websession: Optional[aiohttp.ClientSession] = None,
        local_timezone: Union[str, zoneinfo.ZoneInfo] = REFERENCE_TZ,
        zone_ceuta_melilla: bool = False,
        logger: Optional[logging.Logger] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.source_available = True
        self.state: Optional[float] = None
        self.state_available = False
        self.attributes: Dict[str, Any] = {}

        self.tariff_old = tariff
        if tariff is None:
            self.tariff = None
        else:
            self.tariff = TARIFFS_NEW[1] if zone_ceuta_melilla else TARIFFS_NEW[0]
        self.timeout = timeout

        self._session = websession
        self._with_initial_session = websession is not None
        self._local_timezone = zoneinfo.ZoneInfo(str(local_timezone))
        self._logger = logger or logging.getLogger(__name__)

        self._current_prices: Dict[datetime, float] = {}

        if tariff is None or (
            tariff not in TARIFF_KEYS_NEW and tariff not in TARIFF_KEYS
        ):
            self._logger.warning("Collecting detailed PVPC data for all tariffs")

    async def _download_pvpc_prices(self, day: date) -> Dict[datetime, Any]:
        """
        PVPC data extractor.

        Make GET request to 'api.esios.ree.es' and extract hourly prices for
        the selected tariff from the JSON daily file download
        of the official _Spain Electric Network_ (Red Eléctrica Española, REE)
        for the _Voluntary Price for Small Consumers_
        (Precio Voluntario para el Pequeño Consumidor, PVPC).

        Prices are referenced with datetimes in UTC.
        """
        url = get_url_for_daily_json(day)
        assert self._session is not None
        if day < DATE_CHANGE_TO_20TD:
            tariff = TARIFF_KEYS.get(self.tariff_old) if self.tariff_old else None
        else:
            tariff = TARIFF_KEYS_NEW.get(self.tariff) if self.tariff else None

        try:
            with async_timeout.timeout(self.timeout):
                resp = await self._session.get(url)
                if resp.status < 400:
                    data = await resp.json()
                    return extract_pvpc_data(data, tariff, tz=self._local_timezone)
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
        """
        Update electricity prices from the ESIOS API.

        Input `now: datetime` is assumed tz-aware in UTC.
        If not, it is converted to UTC from the original timezone,
        or set as UTC-time if it is a naive datetime.
        """
        utc_now = _ensure_utc_time(now)
        local_ref_now = utc_now.astimezone(REFERENCE_TZ)
        prices = await self._download_pvpc_prices(local_ref_now.date())
        if not prices:
            return prices

        # At evening, it is possible to retrieve next day prices
        if local_ref_now.hour >= 20:
            next_day = (local_ref_now + timedelta(days=1)).date()
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

        Input `now: datetime` is assumed tz-aware in UTC.
        If not, it is converted to UTC from the original timezone,
        or set as UTC-time if it is a naive datetime.
        """
        tariff = self.tariff
        if utc_now.isoformat() < DATE_CHANGE_TO_20TD.isoformat():
            tariff = self.tariff_old
        attributes: Dict[str, Any] = {"attribution": _ATTRIBUTION, "tariff": tariff}

        def _local(dt_utc: datetime) -> datetime:
            return dt_utc.astimezone(self._local_timezone)

        utc_time = _ensure_utc_time(utc_now.replace(minute=0, second=0, microsecond=0))
        actual_time = _local(utc_time)
        # todo current_period, next_period [P1/P2/P3], next_period_in (hours)
        # todo power_period/power_price €/kW*año
        if len(self._current_prices) > 25 and actual_time.hour < 20:
            # there are 'today' and 'next day' prices, but 'today' has expired
            max_age = (
                utc_time.astimezone(REFERENCE_TZ).replace(hour=0).astimezone(UTC_TZ)
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
        prices_sorted = dict(sorted(self._current_prices.items(), key=lambda x: x[1]))
        attributes["min_price"] = min(self._current_prices.values())
        attributes["min_price_at"] = _local(next(iter(prices_sorted))).hour
        attributes["next_best_at"] = list(
            map(
                lambda x: _local(x).hour,
                filter(lambda x: x >= utc_time, prices_sorted.keys()),
            )
        )

        def _is_tomorrow_price(ts, ref):
            return any(
                map(lambda x: x[0] > x[1], zip(ts.isocalendar(), ref.isocalendar()))
            )

        for ts_utc, price_h in self._current_prices.items():
            ts_local = _local(ts_utc)
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
    ) -> Iterable[Tuple[date, Dict[datetime, Any]]]:
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

        def _adjust_dates(ts: datetime) -> Tuple[datetime, datetime]:
            # adjust dates and tz from inputs to retrieve prices as it was in
            #  Spain mainland, so tz-independent!!
            ts_ref = datetime(
                *ts.timetuple()[:6], tzinfo=self._local_timezone
            ).astimezone(REFERENCE_TZ)
            ts_utc = ts_ref.astimezone(UTC_TZ)
            return ts_utc, ts_ref

        start_utc, start_local = _adjust_dates(start)
        end_utc, end_local = _adjust_dates(end)
        delta: timedelta = end_local.date() - start_local.date()
        days_to_download = [
            start_local.date() + timedelta(days=i) for i in range(delta.days + 1)
        ]

        tic = monotonic()
        max_calls = concurrency_calls
        await self._ensure_session()
        data_days = await self._multi_download(days_to_download, max_calls)
        await self._close_temporal_session()

        prices = {
            hour: hourly_data[hour]
            for (day, hourly_data) in data_days
            for hour in hourly_data
            if start_utc <= hour <= end_utc
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
