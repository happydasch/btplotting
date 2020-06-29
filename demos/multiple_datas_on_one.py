import datetime

import backtrader as bt

from btplotting import BacktraderPlotting


cerebro = bt.Cerebro()

data = bt.feeds.YahooFinanceCSVData(
    dataname="datas/orcl-1995-2014.txt",
    fromdate=datetime.datetime(2000, 1, 1),
    todate=datetime.datetime(2001, 2, 28),
    reverse=False,
    swapcloses=True,
)
cerebro.adddata(data)
data1 = cerebro.resampledata(data, timeframe=bt.TimeFrame.Weeks, compression=1)
data1.plotinfo.plotmaster = data
cerebro.addanalyzer(bt.analyzers.SharpeRatio)

cerebro.run()

p = BacktraderPlotting(style='bar')
cerebro.plot(p)
