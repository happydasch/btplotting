# btplotting

Library to add extended plotting capabilities to `backtrader` (<https://www.backtrader.com/>).

btplotting is a fork based on the awesome `backtrader_plotting` (<https://github.com/verybadsoldier/backtrader_plotting>)

Since most of the inner workings are updated this fork may not
work correctly for you. Please use `backtrader_plotting` instead.

**This fork has some changes compared to backtrader_plotting:**

* No need for custom backtrader
* Different naming / structure
* Live plotting is done using an analyzer
* Navigation in live client (Pausing, Backward, Forward)
* Log panel to also include logging information
* Different data generation which allows to generate data for different datadomains. This is
  useful when replaying data, to remove gaps when using multiple data sources.
* Every figure has its own ColumnDataSource, so the live client can patch without having issues
  with nan values
* Can be extended with custom tabs (for example order execution with live client, custom analysis, etc.)

## Features

* Interactive plots
* Interactive `backtrader` optimization result browser (only supported for single-strategy runs)
* Highly configurable
* Different skinnable themes
* Easy to use

Needs Python >= 3.6.

## Demos

https://happydasch.github.io/btplotting/

## Installation

`pip install git+https://github.com/happydasch/btplotting`

## Live plotting

TODO

## Backtest plotting

TODO

## Plotting Optimization Results

TODO
