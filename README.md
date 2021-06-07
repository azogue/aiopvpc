[![PyPi](https://pypip.in/v/aiopvpc/badge.svg)](https://pypi.org/project/aiopvpc/)
[![Wheel](https://pypip.in/wheel/aiopvpc/badge.svg)](https://pypi.org/project/aiopvpc/)
[![Travis Status](https://travis-ci.org/azogue/aiopvpc.svg?branch=master)](https://travis-ci.org/azogue/aiopvpc)
[![codecov](https://codecov.io/gh/azogue/aiopvpc/branch/master/graph/badge.svg)](https://codecov.io/gh/azogue/aiopvpc)

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
