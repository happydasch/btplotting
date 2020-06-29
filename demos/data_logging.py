from btplotting.panels.log import init_log_panel
from btplotting import BacktraderPlotting
import backtrader as bt
import logging
import datetime


class MyStrategy(bt.Strategy):
    def next(self):
        print(f"close: {self.data.close[0]}")
        logger.info(f"close: {self.data.close[0]}")


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    cerebro = bt.Cerebro()

    init_log_panel([__name__], logging.INFO)

    cerebro.addstrategy(MyStrategy)

    data = bt.feeds.YahooFinanceCSVData(
        dataname="datas/orcl-1995-2014.txt",
        fromdate=datetime.datetime(2000, 1, 1),
        todate=datetime.datetime(2001, 2, 28),
        reverse=False,
        swapcloses=True,
    )
    cerebro.adddata(data)

    cerebro.run()

    p = BacktraderPlotting(style='bar')
    cerebro.plot(p)
