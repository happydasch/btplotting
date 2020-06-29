import datetime

import backtrader as bt

from btplotting import BacktraderPlotting


class MyStrategy(bt.Strategy):
    def __init__(self):
        sma1 = bt.ind.SMA(period=11, subplot=True)
        sma2 = bt.ind.SMA(period=17, plotmaster=sma1)
        sma3 = bt.ind.SMA(sma2, period=5)
        rsi = bt.ind.RSI()
        cross = bt.ind.CrossOver(sma1, sma2)
        a = bt.ind.And(sma1 > sma2, cross)

    def next(self):
        pos = len(self.data)
        if pos == 45 or pos == 145:
            self.buy(self.datas[0], size=None)

        if pos == 116 or pos == 215:
            self.sell(self.datas[0], size=None)


if __name__ == '__main__':
    cerebro = bt.Cerebro()

    cerebro.addstrategy(MyStrategy)

    data = bt.feeds.YahooFinanceCSVData(
        dataname="datas/orcl-1995-2014.txt",
        fromdate=datetime.datetime(2000, 1, 1),
        todate=datetime.datetime(2001, 2, 28),
        reverse=False,
        swapcloses=True,
    )
    cerebro.adddata(data)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio)

    cerebro.run()

    p = BacktraderPlotting(style='bar')
    cerebro.plot(p)
