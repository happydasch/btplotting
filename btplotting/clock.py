import pandas as pd
import backtrader as bt

from bisect import bisect_left
from datetime import timedelta

from .utils import get_dataname, get_source_id


class DataClockHandler:

    '''
    Wraps around a data source for clock generation

    a clock is a index based on a data source on which
    other data sources with a different periods can be
    aligned to.

    If datas period is smaller than the clock period,
    the last data entry in the period of the clock entry
    will be used. All other entries will be discarded.

    the length of the returned data will always be the same
    as the length of the clock. the resulting gaps will be
    filled with nan or the last seen entry.

    the index is 0 based to len(clock) - 1

    examples:

        exmample 1:
            clock entries:
            10:00, 10:05, 10:10
            data entries:
            10:00 10:01, 10:02, 10:03, 10:04, 10:05, 10:06, 10:07

            will result in:
            index   clock   aligned data    fillgaps
            1       10:00   10:04           10:04
            2       10:05   10:07           10:07
            3       10:10   nan             10:07

        example 2:
            clock entries:
            10:00 10:01, 10:02, 10:03, 10:04, 10:05, 10:06, 10:07
            data entries:
            10:00, 10:05

            will result in:
            index   clock   aligned data    fillgaps
            1       10:00   10:00           10:00
            2       10:01   10:00           10:00
            3       10:02   10:00           10:00
            4       10:03   10:00           10:00
            5       10:04   10:00           10:00
            6       10:05   10:05           10:05
            7       10:06   10:05           10:05
            8       10:07   10:05           10:05
    '''

    def __init__(self, strategy, dataname=False):
        clk, tz = self._get_clock_details(strategy, dataname)
        self._strategy = strategy
        self._clk = clk
        self._tz = tz

    def __len__(self):
        '''
        Length of the clock
        '''
        offset = 0
        idx = len(self._clk.array) - 1
        while True:
            if idx < 0:
                break
            val = self._clk.array[idx - offset]
            if val == val:
                break
            offset += 1
        return (idx - offset) + 1  # last valid index + 1

    def _get_clock_details(self, strategy, dataname):
        '''
        Returns clock details (clk, tz)
        '''
        if dataname is not False:
            data = strategy.getdatabyname(dataname)
            return data.datetime, data._tz
        # if no dataname provided, use first data
        return strategy.datetime, strategy.data._tz

    def _align_slice(self, slicedata, startidx=None, endidx=None,
                     fillgaps=False):
        '''
        Aligns a slice to the clock
        '''
        res = []

        # initialize last index used in slicedata
        l_idx = -1 if not len(slicedata['float']) else 0
        maxidx = min(len(slicedata['float']), len(slicedata['value'])) - 1

        # loop through timestamps of curent clock as float values
        dtlist = self.get_dt_list(startidx, endidx, asfloat=True)
        for i in range(0, len(dtlist)):

            # set initial value for this candle
            val = float('nan')
            l_val = float('nan')
            t_start = dtlist[i]
            t_end = dtlist[i + 1] if i < len(dtlist) - 1 else None

            # align slicedata to clock
            while True:
                # there is no data to align, just set nan values
                if l_idx < 0:
                    res.append(val)
                    break

                # all candles from data consumed
                if (l_idx > maxidx):
                    break

                # current values from data
                c_val = slicedata['value'][l_idx]
                c_start = slicedata['float'][l_idx]
                c_end = None
                if t_end and l_idx < maxidx - 1:
                    c_end = slicedata['float'][l_idx + 1]

                # forward until start of clock candle is reached
                # only if current candle is over
                if c_end and c_end < t_start and c_start < t_start:
                    if c_val == c_val:
                        l_val = c_val
                    l_idx += 1
                    continue

                # data belongs to next candle
                if not fillgaps and c_end and c_end > t_end:
                    break

                # set value: either last non nan value or current or nan
                if fillgaps:
                    if c_val != c_val:
                        val = l_val
                    else:
                        val = c_val
                else:
                    if c_val != c_val and l_val == l_val:
                        val = l_val
                    else:
                        val = c_val

                # remember last value for current candle
                l_val = val

                # increment index in slice data if current candle consumed
                if fillgaps and c_end and c_end > t_end:
                    # data is not consumed yet
                    break
                l_idx += 1

            # append the set value to aligned list with values
            res.append(val)

        return res

    def get_idx_for_dt(self, dt):
        return bisect_left(self._clk.array, bt.date2num(dt, tz=self._tz))

    def get_start_end_idx(self, startdt=None, enddt=None, back=None):
        '''
        Returns the startidx and endidx for a given datetime
        '''
        startidx = (
            0
            if startdt is None
            else bisect_left(
                self._clk.array, bt.date2num(startdt, tz=self._tz)))
        if startidx is not None and startidx >= len(self):
            startidx = 0
        endidx = (
            len(self) - 1
            if enddt is None
            else bisect_left(
                self._clk.array, bt.date2num(enddt, tz=self._tz)))
        if endidx is not None and endidx >= len(self):
            endidx = len(self) - 1
        if back:
            if endidx is None:
                endidx = len(self) - 1
            startidx = max(0, endidx - back + 1)
        return startidx, endidx

    def get_dt_at_idx(self, idx, localized=True):
        '''
        Returns a datetime object for given index
        '''
        return bt.num2date(
            self._clk.array[idx],
            tz=None if not localized else self._tz)

    def get_index_list(self, startidx=None, endidx=None, preserveidx=False):
        '''
        Returns a list with int indexes for the clock
        '''
        if startidx is not None:
            startidx = max(0, startidx)
        if endidx is not None:
            endidx = min(len(self), endidx)
        if preserveidx:
            return [int(x) for x in range(startidx, endidx + 1)]
        return [int(x) for x in range(endidx - startidx + 1)]

    def get_dt_list(self, startidx=None, endidx=None, asfloat=False,
                    localized=True):
        '''
        Returns a list with datetime/float indexes for the clock
        '''
        dtlist = []
        for i in self.get_index_list(startidx, endidx, preserveidx=True):
            val = self._clk.array[i]
            if not asfloat:
                val = bt.num2date(val, tz=None if not localized else self._tz)
            dtlist.append(val)
        return dtlist

    def get_slice(self, line, startdt=None, enddt=None):
        '''
        Returns a slice from given line

        This method is used to slice something from another clock for later
        alignment in another clock.
        '''
        res = {'float': [], 'value': []}
        startidx, endidx = self.get_start_end_idx(startdt, enddt)
        for i in self.get_index_list(startidx, endidx, preserveidx=True):
            res['float'].append(self._clk.array[i])
            if i < len(line.array):
                res['value'].append(line.array[i])
            else:
                res['value'].append(float('nan'))
        return res

    def get_data(self, obj, startidx=None, endidx=None,
                 fillgaps=False, fillnan=[]):

        slice_startdt = self.get_dt_at_idx(startidx)
        if endidx < len(self) - 1:
            slice_enddt = (
                self.get_dt_at_idx(endidx + 1) - timedelta(microseconds=1))
        else:
            slice_enddt = None
        dataname = get_dataname(obj)
        tmpclk = DataClockHandler(self._strategy, dataname)
        df = pd.DataFrame()
        source_id = get_source_id(obj)
        for lineidx, line in enumerate(obj.lines):
            alias = obj._getlinealias(lineidx)
            if isinstance(obj, bt.AbstractDataBase):
                if alias == 'datetime':
                    continue
                name = source_id + alias
            else:
                name = get_source_id(line)
            slicedata = tmpclk.get_slice(line, slice_startdt, slice_enddt)
            c_fillgaps = fillgaps or name not in fillnan
            data = self._align_slice(
                slicedata, startidx, endidx, fillgaps=c_fillgaps)
            df[name] = data

        return df
