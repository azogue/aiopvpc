[![PyPI Version][pypi-image]][pypi-url]
[![pre-commit.ci Status][pre-commit-ci-image]][pre-commit-ci-url]
[![Build Status][build-image]][build-url]
[![Code Coverage][coverage-image]][coverage-url]
<!-- Badges -->
[pypi-image]: https://img.shields.io/pypi/v/aiopvpc
[pypi-url]: https://pypi.org/project/aiopvpc/
[pre-commit-ci-image]: https://results.pre-commit.ci/badge/github/azogue/aiopvpc/master.svg
[pre-commit-ci-url]: https://results.pre-commit.ci/latest/github/azogue/aiopvpc/master
[build-image]: https://github.com/azogue/aiopvpc/actions/workflows/main.yml/badge.svg
[build-url]: https://github.com/azogue/aiopvpc/actions/workflows/main.yml
[coverage-image]: https://codecov.io/gh/azogue/aiopvpc/branch/master/graph/badge.svg
[coverage-url]: https://codecov.io/gh/azogue/aiopvpc

# aiopvpc

Simple aio library to download Spanish electricity hourly prices.

Made to support the [**`pvpc_hourly_pricing`** HomeAssistant integration](https://www.home-assistant.io/integrations/pvpc_hourly_pricing/).

<span class="badge-buymeacoffee"><a href="https://www.buymeacoffee.com/azogue" title="Donate to this project using Buy Me A Coffee"><img src="https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg" alt="Buy Me A Coffee donate button" /></a></span>


## Install

Install with `pip install aiopvpc` or clone it to run tests or anything else.

## Usage

```python
import aiohttp
from datetime import datetime
from aiopvpc import PVPCData

async with aiohttp.ClientSession() as session:
    pvpc_handler = PVPCData(session=session, tariff="2.0TD")
    prices: dict = await pvpc_handler.async_update_prices(datetime.utcnow())
print(prices)
```
