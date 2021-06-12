# Changelog

## [v2.2.0](https://github.com/azogue/aiopvpc/tree/v2.2.0) - New sensor attributes for new tariff 2.0TD (2021-06-12)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.2.0...v2.1.2)

**Changes:**

* Determine tariff period (P1/P2/P3) for current hour, and calculate the delta hours to the next one, publishing attributes `period`, `next_period`, and `hours_to_next_period`
* Add `price_ratio`, `max_price`, and `max_price_at` attributes
* When there are cheaper prices ahead, add attributes `next_better_price`, `hours_to_better_price`, and `num_better_prices_ahead`
* Add `price_position` attribute (1 for cheaper price, 24 for the most high-priced), as suggested by @r-jordan in #23
* Add contracted power in kW as new parameters (power for P1/P2 and power for P3) to show the `available_power` for each period
* Use `holidays` library to retrieve national holidays where to apply the valley period P3 for the full day

## [v2.1.2](https://github.com/azogue/aiopvpc/tree/v2.1.2) - Quick adapt to new tariff 2.0TD (2021-05-31)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.1.2...v2.1.1)

**Changes:**

- Use "PCB" and "CYM" keys to retrieve prices for dates > 2021-06-01 to match new JSON from Esios API for new '2.0 TD' tariff.
- Add new flag to set prices for Ceuta & Melilla (to use "CYM" identifier instead of "PCB")

## [v2.1.1](https://github.com/azogue/aiopvpc/tree/v2.1.1) - Fix prices badly assigned outside default timezone (2021-05-16)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.1.1...v2.0.2)

**Changes:**

- Remove `pytz` dependency and handle timezones with `zoneinfo` (related to [this article](https://developers.home-assistant.io/blog/2021/05/07/switch-pytz-to-python-dateutil)),
  and adapt to use input timezone as a time zone object or a string identifier.
- **Fix prices being badly assigned in Canary Islands timezone**.
  Before, prices where **assumed absolute in time**, and marked with tz-aware UTC datetimes,
  but that behavior was incorrect 😔, as prices are applicable _by-hour_, independently of the timezone.
  So now the produced prices are **shifted**, to apply the correct ones for each local hour, so given the price at 10AM,
  it will be the same across all timezones. THIS IS A **BREAKING CHANGE** over the old behavior, if you live in the Canary Islands (because before the prices were incorrect!)
- Fix sensor attributes in month changes (there were badly tagged as "price last day" instead of "price next day" 🤪).
- Update tests suite to use `pytest-asyncio` instead of `pytest-aiohttp`, add `mypy` to pre-commit, and a general dependency update.

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
