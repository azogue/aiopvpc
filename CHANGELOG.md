# Changelog

## [v2.1.0](https://github.com/azogue/aiopvpc/tree/v2.1.0) - Fix prices being in local time (2021-01-24)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.1.0...v2.0.2)

**Changes:**

- **Fix prices being badly assigned in Canary Islands timezone**. Before, prices where assumed absolute in time, and marked with **tz-aware UTC datetimes**, but that behavior is incorrect, as prices are applicable _by-hour_, independently of the timezone. So now the prices are **returned in the local timezone** (so, _tz-aware_, just not UTC, probably), so given price at 10AM is the same across all timezones. THIS IS A **BREAKING CHANGE**.
- Fix sensor attributes in month changes (there were badly tagged as "price last day" instead of "price next day").

## [v2.0.2](https://github.com/azogue/aiopvpc/tree/v2.0.2) - Unpinned requirements (2020-08-04)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.0.1...v2.0.2)

**Changes:**

- Fix outdated pinned requirements by setting just a minimal version, and syncing those with HomeAssistant

## [v2.0.1](https://github.com/azogue/aiopvpc/tree/v2.0.1) - Add methods to download a range of days (2020-05-07)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v1.0.2...v2.0.1)

**Implemented enhancements:**

- Async & blocking methods to download prices for a range of days.
- Use an `asyncio.Queue` to control concurrency for downloading a bunch of days, by creating a `concurrency_calls` number of workers.
- Make specific tariff optional, to get ALL PVPC detailed data when None, with schema `Dict[datetime, Dict[str, float]` instead of tariff-specific `Dict[datetime, float]`.

**Changes:**

- Make rest of init parameters also optional, to easier instantiation with `PVPCData()`.
- Add minimal doc in README and an example of use for bulk download of PVPC prices

## [v1.0.2](https://github.com/azogue/aiopvpc/tree/v1.0.2) - Fix timezone support outside Europe/Madrid zone.

## [1.0.0] - Initial

**Implemented**

- Basic data handler `PVPCData` to `.async_update_prices` and `process_state_and_attributes` for the PVPC HA sensor.
