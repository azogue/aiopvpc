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
from datetime import datetime
from aiopvpc import PVPCData

pvpc_handler = PVPCData(tariff="discrimination", zone_ceuta_melilla=False)

start = datetime(2021, 5, 20, 22)
end = datetime(2021, 6, 7, 16)
prices_range: dict = await pvpc_handler.async_download_prices_for_range(start, end)
```

Check [this example on a jupyter notebook](https://github.com/azogue/aiopvpc/blob/master/Notebooks/Download%20PVPC%20prices.ipynb), where the downloader is combined with pandas and matplotlib to plot the electricity prices.
To play with it, clone the repo and install the project with `poetry install -E jupyter`, and then `poetry run jupyter notebook`.

![sample_pvpc_plot.png](https://github.com/azogue/aiopvpc/blob/master/Notebooks/sample_pvpc_plot.png)
