# btplotting

Library to add extended plotting capabilities to `backtrader` (<https://www.backtrader.com/>) using bokeh.

btplotting is a fork based on the awesome `backtrader_plotting` (<https://github.com/verybadsoldier/backtrader_plotting>)

Since most of the inner workings are changed, this fork may not
work correctly for you. Please use `backtrader_plotting` instead.

**What is different:**

Basic:

* No need for custom backtrader
* Different naming / structure
* Different data generation which allows to generate data for different data sources. This is
  useful when replaying or resampling data, for example to remove gaps.
* Support for replay data
* Every figure has its own ColumnDataSource, so the live client can patch without having issues
  with nan values, every figure is updated individually
* Display of plots looks more like backtrader plotting (order, heights, etc.)
* Allows to add custom columns (for example colors, fill columns, etc.)

Plotting:

* Datas, Indicators, Observer and Volume have own aspect ratios
* Only one axis for volume will be added when using multiple data sources on one figure
* Volume axis position is configureable
* Linked Crosshair across all figures
* fill_gt, fill_lt, fill support

Tabs:

* Default tabs can be completely removed
* New log panel to also include logging information
* Can be extended with custom tabs (for example order execution with live client, custom analysis, etc.)

Live plotting:

* Navigation in live client (Pause, Backward, Forward)
* Live plotting is done using an analyzer
* Live plotting data update works in a single thread and is done by a DataHandler
* Data update is being done every n seconds, this is configureable

## Features

* Interactive plots
* Interactive `backtrader` optimization result browser (only supported for single-strategy runs)
* Highly configurable
* Different skinnable themes
* Easy to use

Python >= 3.6 is required.

## Demos

<https://happydasch.github.io/btplotting/>

## Installation

`pip install git+https://github.com/happydasch/btplotting`

## Live plotting

TODO

## Backtest plotting

TODO

## Plotting Optimization Results

TODO
