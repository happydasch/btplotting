# btplotting

Library to add extended plotting capabilities to `backtrader` (<https://www.backtrader.com/>) using bokeh.

btplotting is based on the awesome `backtrader_plotting` (<https://github.com/verybadsoldier/backtrader_plotting>)

`btplotting` is a complete rework of `backtrader_plotting` with the live client in focus. Besides this, a lot of
issues are fixed and new functionality is added. See the list below for differences.

**What is different:**

Basic:

* No need for custom backtrader
* Different naming / structure
* Different data generation which allows to generate data for different data sources.
  This is useful when replaying or resampling data, for example to remove gaps.
* Different filtering of plot objects
* Support for replay data
* Every figure has its own ColumnDataSource, so the live client can patch without
  having issues with nan values, every figure is updated individually
* Display of plots looks more like backtrader plotting (order, heights, etc.)
* Allows to generate custom columns, which don't have to be hardcoded. This is being used to generate
  color for candles, varea values, etc.
* Possibility to fill gaps of higher timeframes with data

Plotting:

* Datas, Indicators, Observer and Volume have own aspect ratios, which can be configured in live client
  or scheme
* Only one axis for volume will be added when using multiple data sources on one figure
* Volume axis position is configureable in scheme, by default it is being plotted on the right side
* Linked Crosshair across all figures
* fill_gt, fill_lt, fill support
* Plot objects can be filtered by one or more datanames or by plot group
* Custom plot group, which can be configured in app or in live client by providing all
  plotids in a comma-seperated list or by selecting the parts of the plot to display

Tabs:

* Default tabs can be completely removed
* New log panel to also include logging information
* Can be extended with custom tabs (for example order execution with live client, custom analysis, etc.)

Live plotting:

* Navigation in live client (Pause, Backward, Forward)
* Live plotting is done using an analyzer, so there is no need to use custom backtrader
* Live plotting data update works in a single thread and is done by a DataHandler
* Data update is being done every n seconds, which is configureable

## Features

* Interactive plots
* Interactive `backtrader` optimization result browser (only supported for single-strategy runs)
* Highly configurable
* Different skinnable themes
* Easy to use

Python >= 3.6 is required.


## How to use
* Add to cele as an analyzer:
```python
from btplotting import BacktraderPlottingLive
  ...
  ...

cerebro = bt.Cerebro()
cerebro.addstrategy(MyStrategy)
cerebro.adddata(LiveDataStream())
cerebro.addanalyzer(BacktraderPlottingLive)
cerebro.run()
cerebro.plot()
```

* If you need to change the default port or share the plotting to public:

```python
cerebro.addanalyzer(BacktraderPlottingLive, address="*", port=8889)
```

## Jupyter

In Jupyter you can plut to a single browser tab with iplot=False:

```python
plot = btplotting.BacktraderPlotting()
cerebro.plot(plot, iplot=False)
```

You may encounters TypeError: `<class '__main__.YourStrategyClass'>` is a built-in class error.

To remove the source code tab use:

```python
plot = btplotting.BacktraderPlotting()
plot.tabs.remove(btplotting.tabs.SourceTab)
cerebro.plot(plot, iplot=False)
```

## Demos

<https://happydasch.github.io/btplotting/>

## Installation

`pip install git+https://github.com/happydasch/btplotting`

## Sponsoring

If you want to support the development of btplotting, consider to support this project.

* BTC: 39BJtPgUv6UMjQvjguphN7kkjQF65rgMMF
* ETH: 0x06d6f3134CD679d05AAfeA6e426f55805f9B395D
* <https://liberapay.com/happydasch>
