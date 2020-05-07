# Changelog

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
