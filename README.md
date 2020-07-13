# btplotting

Library to add extended plotting capabilities to `backtrader` (<https://www.backtrader.com/>).

btplotting is a fork based on the awesome `backtrader_plotting` (<https://github.com/verybadsoldier/backtrader_plotting>)

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

## Features

* Interactive plots
* Interactive `backtrader` optimization result browser (only supported for single-strategy runs)
* Highly configurable
* Different skinnable themes
* Easy to use

Needs Python >= 3.6.

## Installation

`pip install git+https://github.com/happydasch/btplotting`

## Live plotting

TODO

## Backtest plotting

TODO

## Plotting Optimization Results

TODO