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
    '''

    def __init__(self, strategy, dataname=False):
        clk, tz = self._get_clk_details(strategy, dataname)
        self._strategy = strategy
        self._dataname = dataname
        self._clk = clk
        self._tz = tz
        if not dataname:
            data = strategy.data
        else:
            data = strategy.getdatabyname(dataname)
        self._rightedge = data.p._get('rightedge', True)

        self._clk_cache = None
        self.last_endidx = -1

    def __len__(self):
        '''
        Length of the clock
        '''
        if not self._clk_cache:
            return len(self._clk)

        offset = 0

        # clk = self._get_clk()
        clk = self._clk_cache

        idx = len(clk) - 1
        while True:
            if idx < 0:
                break
            val = clk[idx - offset]
            if val == val:
                break
            offset += 1
        return (idx - offset) + 1  # last valid index + 1

    def init_clk(self):
        # for live data, self._clk might change so we cache it
        last_index = len(self._clk)
        last_one = self._clk.array[-1]
        if last_one != last_one:
            last_index -= 1

        # self._clk_cache = sorted(set(self._clk.array[-len(self._clk) + 1: last_index]))
        self._clk_cache = sorted(set(self._clk.array[: last_index]))

    def uinit_clk(self, last_endidx):
        assert self._clk_cache, "init_clk should have been called"
        self._clk_cache = None
        self.last_endidx = last_endidx

    # def _get_clk(self):
    #     '''
    #     Returns the clock to use
    #     '''
    #     # ensure clk has unique values also use only reported len
    #     # of data from clock
    #     # return sorted(set(self._clk.array[-len(self._clk)+1:]))
    #     return self.clk_cache

    def _get_clk_details(self, strategy, dataname):
        '''
        Returns clock details (clk, tz)
        '''
        if dataname is not False:
            data = strategy.getdatabyname(dataname)
            return data.datetime, data._tz or strategy.data._tz
        # if no dataname provided, use first data
        return strategy.datetime, strategy.data._tz

    def _align_slice(self, slicedata, startidx=None, endidx=None,
                     rightedge=True):
        '''
        Aligns a slice to the clock
        '''
        res = []

        # loop through timestamps of curent clock as float values
        dtlist = self.get_dt_list(startidx, endidx, asfloat=True)
        # initialize last index used in slicedata
        l_idx = -1 if not len(slicedata['float']) else 0
        maxidx = min(len(slicedata['float']), len(slicedata['value'])) - 1
        for i in range(0, len(dtlist)):
            # set initial value for this candle
            t_val = float('nan')  # target candle value
            if rightedge:
                t_end = dtlist[i]
                t_start = t_end
                if len(dtlist) > 1:
                    if i == 0:
                        t_start = t_end - (dtlist[1] - dtlist[0])
                    else:
                        t_start = dtlist[i - 1]
            else:
                t_start = dtlist[i]
                t_end = t_start
                if i < len(dtlist) - 1:
                    t_end = dtlist[i + 1]
                elif len(dtlist) > 1:
                    t_end = t_start + dtlist[1] - dtlist[0]
            # align slicedata to target clock
            while True:
                # there is no data to align, just set nan values
                if l_idx < 0:
                    res.append(t_val)
                    break
                # all candles from data consumed
                if (l_idx > maxidx):
                    break
                # get duration of current candle
                # current values from data
                c_val = slicedata['value'][l_idx]
                if rightedge:
                    c_end = slicedata['float'][l_idx]
                    c_start = None
                    if maxidx > 1:
                        if l_idx == 0:
                            c_start = (c_end - (slicedata['float'][1]
                                                - slicedata['float'][0]))
                        else:
                            c_start = slicedata['float'][l_idx - 1]
                else:
                    c_start = slicedata['float'][l_idx]
                    c_end = None
                    if l_idx < maxidx - 1:
                        c_end = slicedata['float'][l_idx + 1]
                    elif maxidx > 1:
                        c_end = (c_start + (slicedata['float'][1]
                                            - slicedata['float'][0]))
                # check if value belongs to next candle, if current value
                # belongs to next target candle don't use this value and
                # stop here and use previously set value
                if c_start and c_start > t_end:
                    break
                # forward until start of target start is readched
                # move forward in source data and remember the last value
                # of the candle, also don't process further if last candle
                # and after start of target
                if c_end and c_end <= t_start:
                    l_idx += 1
                    continue
                # set target value
                if c_val == c_val:
                    t_val = c_val
                # increment index in slice data if current candle consumed
                l_idx += 1
            # append the set value to aligned list with values
            res.append(t_val)
        return res

    def get_idx_for_dt(self, dt):
        clk = self._clk_cache
        assert clk, "wrong"
        return bisect_left(clk, bt.date2num(dt, tz=self._tz))

    def get_start_end_idx(self, startdt=None, enddt=None, back=None):
        '''
        Returns the startidx and endidx for a given datetime
        '''
        clk = self._clk_cache
        assert clk, "wrong"
        startidx = (
            0
            if startdt is None
            else bisect_left(clk, bt.date2num(startdt, tz=self._tz)))
        if startidx is not None and startidx >= len(clk):
            startidx = 0
        endidx = (
            len(clk) - 1
            if enddt is None
            else bisect_left(clk, bt.date2num(enddt, tz=self._tz)))
        if endidx is not None and endidx >= len(clk):
            endidx = len(clk) - 1
        if back:
            if endidx is None:
                endidx = len(clk) - 1
            startidx = max(0, endidx - back + 1)
        return startidx, endidx

    def get_dt_at_idx(self, idx, localized=True):
        '''
        Returns a datetime object for given index
        '''
        clk = self._clk_cache
        assert clk, "wrong"
        return bt.num2date(
            clk[idx],
            tz=None if not localized else self._tz)

    def get_idx_list(self, startidx=None, endidx=None, preserveidx=True):
        '''
        Returns a list with int indexes for the clock
        '''
        clk = self._clk_cache
        assert clk, "wrong"
        if startidx is not None:
            startidx = max(0, startidx)
        if endidx is not None:
            endidx = min(len(clk), endidx)
        if preserveidx:
            return [int(x) for x in range(startidx, endidx + 1)]
        return [int(x) for x in range(endidx - startidx + 1)]

    def get_dt_list(self, startidx=None, endidx=None, asfloat=False,
                    localized=True):
        '''
        Returns a list with datetime/float indexes for the clock
        '''
        clk = self._clk_cache
        assert clk, "wrong"
        dtlist = []
        for i in self.get_idx_list(startidx, endidx):
            val = clk[i]
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
        clk = self._clk_cache
        assert clk, "wrong"
        res = {'float': [], 'value': []}
        startidx, endidx = self.get_start_end_idx(startdt, enddt)
        for i in self.get_idx_list(startidx, endidx):
            res['float'].append(clk[i])
            if i < len(line.array):
                res['value'].append(line.array[i])
            else:
                res['value'].append(float('nan'))
        return res

    def get_data(self, obj, startidx=None, endidx=None,
                 fillnan=[], skipnan=[]):
        '''
        Returns data from object aligned to clock
        '''
        clk = self._clk_cache
        assert clk, "wrong"
        slice_startdt = self.get_dt_at_idx(startidx)
        if endidx < len(clk) - 1:
            slice_enddt = (
                self.get_dt_at_idx(clk, endidx + 1) - timedelta(microseconds=1))
        else:
            slice_enddt = None
        # dataname = get_dataname(obj)
        # tmpclk = DataClockHandler(self._strategy, dataname)
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
            slicedata = self.get_slice(line, slice_startdt, slice_enddt)
            data = self._align_slice(
                slicedata, startidx, endidx, rightedge=self._rightedge)
            df[name] = data
            # make sure all data is filled correctly,
            # either interpolate if skipnan
            # or forward fill if not fillnan
            if name in skipnan:
                df[name] = df[name].interpolate()
            elif name not in fillnan:
                df[name] = df[name].fillna(method='ffill')
        return df
