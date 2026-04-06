# Changelog

## [v4.3.1](https://github.com/azogue/aiopvpc/tree/v4.3.1) - 🐛 Fix unsorted prices in composed sensor 'INDEXED' (2024-03-25)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v4.3.0...v4.3.1)

- 🐛 Fix unsorted prices in composed sensor 'INDEXED' (#72)
- 👷 ci: Split actions for tests on PRs and publish package on main
- 👷 Remove codecov integration and produce reports instead (#71)

## [v4.3.0](https://github.com/azogue/aiopvpc/tree/v4.3.0) - ✨ Add new _composed_ sensor for Indexed tariff (2024-03-10)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v4.2.2...v4.3.0)

- ✨ Add new price sensors: **Market adjustment** (from ESIOS API indicator 2108), and **Indexed tariff** (as _composed_ price sensor calculated as `PVPC - ADJUSTMENT`), from first-time contributor @MiguelAngelLV in #69 🍻, and some adjustments in #70
- 🎨 pre-commit updates and change to `ruff` + `ruff-format` instead of `black` and `isort`
- 🚀 Bump minor version and update deps and CHANGELOG.md

## [v4.2.2](https://github.com/azogue/aiopvpc/tree/v4.2.2) - ♻️ Remove python upper limit (2023-07-30)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v4.2.1...v4.2.2)

- ♻️ Remove python upper limit (from @cdce8p in #59)
- 🎨 pre-commit autoupdate
- 📦️ Bump minor version and update deps and CHANGELOG.md

## [v4.2.1](https://github.com/azogue/aiopvpc/tree/v4.2.1) - Fix injection price sensor attributes (2) (2023-05-29)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v4.2.0...v4.2.1)

- 🐛 Fix one-line conditional matching for 'not None' instead of positive value 🙈
- ✅ tests: Add unit test for price sensor attributes

## [v4.2.0](https://github.com/azogue/aiopvpc/tree/v4.2.0) - Fix injection price sensor attributes (2023-05-29)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v4.1.0...v4.2.0)

- 🐛 Fix attributes 'max_price_at' and 'min_price_at' for injection price sensor (were swapped)
- 📦️ Bump minor version and update deps
- 📝 Fix usage example in README.md
- 🎨 pre-commit autoupdate and swap `flake8` for `ruff`
- 📝 Fix links in CHANGELOG.md

## [v4.1.0](https://github.com/azogue/aiopvpc/tree/v4.1.0) - Adapt to 403 unauthorized error (2023-03-12)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v4.0.1...v4.1.0)

- 🐛 Process 403 error from server like '401 unauthorized', raising `BadApiTokenAuthError`
  to signal HA for reauth-config for both status codes, when API token is enabled.

## [v4.0.1](https://github.com/azogue/aiopvpc/tree/v4.0.1) - Minor fixes (2023-01-11)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v4.0.0...v4.0.1)

- ✏️ Fix typo on 'injection' keyword (was badly typed as _spanglish_ 'inyection' 😅)
- 🐛 Fix unit for price sensors attributes (from €/MWh to €/kWh)

## [v4.0.0](https://github.com/azogue/aiopvpc/tree/v4.0.0) - Implement ESIOS API Token (2023-01-09)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v3.0.0...v4.0.0)

- ✨ Implement **support to access the extended ESIOS API** with a personal token
  (you must request yours by mailing to [consultasios@ree.es](mailto:consultasios@ree.es?subject=Personal%20token%20request)),
  with initial support for the existent PVPC price sensor (ESIOS indicator code: **1001**), and **3 new ones** 🤩:
  - **Inyection price** sensor (ESIOS indicator code: **1739**),
    name: "Precio de la energía excedentaria del autoconsumo para el mecanismo de compensación simplificada"
  - **MAG price** sensor (ESIOS indicator code: **1900**),
    name: "Desglose peaje por defecto 2.0TD excedente o déficit de la liquidación del mecanismo de ajuste de costes de producción"
  - **OMIE price** sensor (ESIOS indicator code: **10211**),
    name: "Precio medio horario final suma de componentes"

- 💥 Remove 'apidatos' support as alternative _data-source_, leaving only public and private paths for https://api.esios.ree.es

- ✨ Signal bad auth for esios token calls with a custom exception, to handle 'reauth' flow in Home-Assistant

- ✨ Add helper methods for HA integration to manage unique ids for each sensor, to update the enabled sensors to download, and to check the API token

- ♻️ Use dataclasses for `EsiosApiData` and `EsiosResponse` data containers, instead of typed dicts

- ✅ tests: Update fixtures for esios sensors and adapt tests to the new interface and the multiple-sensors behaviour

- 📦️ Bump mayor version to **v4** and lighten dev-env, removing pre-commit related modules and adding python-dotenv

- (from #46, with v3.1.0) Remove `holidays` dependency to evaluate special days under 'P3' period and fix tests

## [v3.0.0](https://github.com/azogue/aiopvpc/tree/v3.0.0) - Change Data Source to apidatos.ree.es (2021-12-05)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.3.0...v3.0.0)

🔥 **BREAKING-CHANGE**: this release **removes support for the old PVPC tariffs**
(prices < 2021-06-01), and the extra methods to use this library as a _dataloader_
(`.download_prices_for_range(...)`), leaving only the **code to support the HA Core integration**.

Motivated by recent successful attempts to kick us out from `api.esios.ree.es`,
we are changing the data source to another REE public server, at `apidatos.ree.es`,
with the same information than the current one, available without authentication 👌

**This release implements the new data-source**, but also maintains the _legacy_ one.

- Initial configuration is set with a new `data_source` parameter, **with the new source as default**.
- If a 403 status-code is received, the **data source is switched** (new to legacy / legacy to new), no retry is done,
  and the User-Agent loop trick is only used for the legacy data-source.

**Changes:**

- :fire: Remove support for old PVPC tariffs and range download methods,
  and make `tariff` and `websession` required arguments

- :sparkles: Add alternative data-source from 'apidatos.ree.es'
  - Implement data parsing from `apidatos.ree.es`, using endpoint at `/es/datos/mercados/precios-mercados-tiempo-real`
  - Add `data_source` parameter with valid keys 'apidatos' and 'esios_public', setting the new one as default ;-)
  - Remove retry call if 403 status is received, but maintain the User-Agent loop, and also toggle the data-source for the next call
  - Move old ATTRIBUTION to `.attribution` property, as function of the data-source

- :truck: Change test patterns to new tariffs by substituting old examples in DST days from 2019 to equivalent days since 2021-06, using the new tariff keys

- :truck: Add test patterns from new data-source, and adjust tests

## [v2.3.0](https://github.com/azogue/aiopvpc/tree/v2.3.0) - Decrease API refresh rate and try to avoid banning (2021-12-01)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.2.4...v2.3.0)

Quick-Fix Release motivated by the last change in the ESIOS server (on 2021-11-30 😱),
which is now apparently banning HomeAssistant requests,
filtering us out because of the 'User-Agent' headers data 😤,
as the server is returning a 403 status code error for a PUBLIC url 🤷.

**Changes:**

- :zap: **Substantially decrease the number of API requests to ESIOS**,
  avoiding unnecesary calls to refresh data for the same electricity prices.
  Before, when used from the `pvpc_hourly_pricing` HA Core integration,
  the ESIOS API was called 2 times/hour from 0h to 20h, and 4 times/hour in the evening,
  from 20h to 0h, retrieving today + tomorrow prices.
  This makes a total of ~56 requests/day, which is _not a lot_ 😅,
  but it seems the aggregated total for the HA user base (🔥 >30k requests/day just
  counting users pushing HA analytics) is being some kind of a problem for ESIOS,
  as it looks like they're trying to bane us 🥺😭
  Now, the API handler avoids calls to retrieve already available prices,
  cutting down the number of requests to just 1-2 requests/day 🤩

- :bug: **Set standard `User-Agent` header info**, to try to avoid server-side banning 🙈,
  and _rotate_ it if banning is detected, using common User-Agent browser identifiers.

- :recycle: Minor code refactor to prepare for future library changes, in order to move to authenticated API endpoints in future versions.

## [v2.2.4](https://github.com/azogue/aiopvpc/tree/v2.2.4) - Split today / tomorrow price sensor attributes (2021-11-20)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.2.2...v2.2.4)

**Changes:**

- Generate different sets of sensor attributes for hourly prices for current day and for the next day (available at evening), so attrs like `price_position` or `price_ratio` don't change for the current day when next-day prices are received.

## [v2.2.2](https://github.com/azogue/aiopvpc/tree/v2.2.2) - Migrate CI from travis to gh-actions (2021-11-04)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.2.1...v2.2.2)

**Changes:**

- :art: Add isort to pre-commit config
- :green_heart: Add configuration for pre-commit.ci to run linter checks there
- :green_heart: CI flow with GitHub Actions to
  - install library with `poetry`
  - run tests
  - upload coverage when merging to master
  - publish a new pypi version when merging to master if `pyproject.toml` changes
- :fire: Remove previus travis CI config

## [v2.2.1](https://github.com/azogue/aiopvpc/tree/v2.2.1) - Quickfix for 403 status code from ESIOS API (2021-11-03)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.2.0...v2.2.1)

**Changes:**

- Fix Esios request returning a 403 status code since 2021-11-02, by:
  - just adding an 'User-Agent' to request headers, if `aiohttp==3.7.4.post0`
  - or upgrading to `aiohttp==3.8.0`, where it is not needed and the original request works like before
- Add better error logging for this 'forbidden' error if reappears in the future
- Update deps, requiring holidays>0.11.1

## [v2.2.0](https://github.com/azogue/aiopvpc/tree/v2.2.0) - New sensor attributes for new tariff 2.0TD (2021-06-12)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.1.2...v2.2.0)

**Changes:**

- Determine tariff period (P1/P2/P3) for current hour, and calculate the delta hours to the next one, publishing attributes `period`, `next_period`, and `hours_to_next_period`
- Add `price_ratio`, `max_price`, and `max_price_at` attributes
- When there are cheaper prices ahead, add attributes `next_better_price`, `hours_to_better_price`, and `num_better_prices_ahead`
- Add `price_position` attribute (1 for cheaper price, 24 for the most high-priced), as suggested by @r-jordan in #23
- Add contracted power in kW as new parameters (power for P1/P2 and power for P3) to show the `available_power` for each period
- Use `holidays` library to retrieve national holidays where to apply the valley period P3 for the full day

## [v2.1.2](https://github.com/azogue/aiopvpc/tree/v2.1.2) - Quick adapt to new tariff 2.0TD (2021-05-31)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.1.1...v2.1.2)

**Changes:**

- Use "PCB" and "CYM" keys to retrieve prices for dates > 2021-06-01 to match new JSON from Esios API for new '2.0 TD' tariff.
- Add new flag to set prices for Ceuta & Melilla (to use "CYM" identifier instead of "PCB")

## [v2.1.1](https://github.com/azogue/aiopvpc/tree/v2.1.1) - Fix prices badly assigned outside default timezone (2021-05-16)

[Full Changelog](https://github.com/azogue/aiopvpc/compare/v2.0.2...v2.1.1)

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
