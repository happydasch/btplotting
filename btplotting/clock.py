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
        clk, tz = self._get_clk_details(strategy, dataname)
        self._strategy = strategy
        self._dataname = dataname
        self._clk = clk
        self._tz = tz

    def __len__(self):
        '''
        Length of the clock
        '''
        offset = 0
        clk = self._get_clk()
        idx = len(clk) - 1
        while True:
            if idx < 0:
                break
            val = clk[idx - offset]
            if val == val:
                break
            offset += 1
        return (idx - offset) + 1  # last valid index + 1

    def _get_clk(self):
        '''
        Returns the clock to use
        '''
        # ensure clk has unique values also use only reported len
        # of data from clock
        return sorted(set(self._clk.array[-len(self._clk)+1:]))

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
                     fillgaps=False, rightedge=True):
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
            p_val = float('nan')  # previous candle value in current candle
            t_val = float('nan')  # target candle value
            if rightedge:
                t_end = dtlist[i] - 1e-6
                if i == 0:
                    if len(dtlist) > 1:
                        duration = dtlist[1] - dtlist[0]
                    else:
                        duration = 0
                else:
                    duration = dtlist[i] - dtlist[i - 1]
                t_start = t_end - duration
            else:
                t_start = dtlist[i]
                if i < len(dtlist) - 1:
                    duration = dtlist[i + 1] - dtlist[i]
                else:
                    if len(dtlist) > 1:
                        duration = dtlist[1] - dtlist[0]
                    else:
                        duration = 0
                t_end = t_start + duration - 1e-6
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
                    if l_idx == 0:
                        if maxidx > 1:
                            c_duration = (slicedata['float'][1]
                                          - slicedata['float'][0])
                        else:
                            c_duration = 0
                    else:
                        c_duration = (slicedata['float'][l_idx]
                                      - slicedata['float'][l_idx - 1])
                    c_start = c_end - c_duration
                else:
                    c_start = slicedata['float'][l_idx]
                    if l_idx < maxidx - 1:
                        c_duration = (slicedata['float'][l_idx + 1]
                                      - slicedata['float'][l_idx])
                    else:
                        if maxidx > 1:
                            c_duration = (slicedata['float'][1]
                                          - slicedata['float'][0])
                        else:
                            duration = 0
                    c_end = c_start + c_duration
                # check if value belongs to next candle, if current value
                # belongs to next target candle don't use this value and
                # stop here and use previously set value
                if not fillgaps and c_start > t_end:
                    break
                # forward until start of target start is readched
                # move forward in source data and remember the last value
                # of the candle, also don't process further if last candle
                # and after start of target
                if ((c_end and c_end < t_start and c_start < t_start)
                        or (not c_end and c_start > t_start)):
                    # if current value is a non-nan value remember it
                    if c_val == c_val:
                        p_val = c_val
                    l_idx += 1
                    continue
                # set value: either last non-nan value or current or nan
                if fillgaps:
                    # when filling gaps either nan if no previous value
                    # previous value if current value is nan
                    # else current value
                    if c_val != c_val:
                        t_val = p_val
                    else:
                        t_val = c_val
                else:
                    # set target value
                    if c_val == c_val:
                        t_val = c_val
                # data is not consumed yet, if filling gaps, keep this value
                if fillgaps and c_end and c_end > t_end:
                    break
                # increment index in slice data if current candle consumed
                l_idx += 1
            # append the set value to aligned list with values
            res.append(t_val)
            # remember last value for current candle
            if t_val == t_val:
                p_val = t_val
        return res

    def get_idx_for_dt(self, dt):
        clk = self._get_clk()
        return bisect_left(clk, bt.date2num(dt, tz=self._tz))

    def get_start_end_idx(self, startdt=None, enddt=None, back=None):
        '''
        Returns the startidx and endidx for a given datetime
        '''
        clk = self._get_clk()
        startidx = (
            0
            if startdt is None
            else bisect_left(clk, bt.date2num(startdt, tz=self._tz)))
        if startidx is not None and startidx >= len(self):
            startidx = 0
        endidx = (
            len(self) - 1
            if enddt is None
            else bisect_left(clk, bt.date2num(enddt, tz=self._tz)))
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
        clk = self._get_clk()
        return bt.num2date(
            clk[idx],
            tz=None if not localized else self._tz)

    def get_idx_list(self, startidx=None, endidx=None, preserveidx=True):
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
        clk = self._get_clk()
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
        clk = self._get_clk()
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
                 fillgaps=False, fillnan=[]):
        '''
        Returns data from object aligned to clock
        '''
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
