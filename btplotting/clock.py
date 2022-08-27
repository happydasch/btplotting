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
        last_idx = -1 if not len(slicedata['float']) else 0
        last_val = float('nan')
        # loop through timestamps of curent clock as float values
        dtlist = self.get_dt_list(startidx, endidx, asfloat=True)
        for i in range(0, len(dtlist)):
            # set initial value for this candle
            val = float('nan') if not fillgaps else last_val
            # get the time range for current clock candle
            startdt = dtlist[i]
            enddt = None
            # only set a end date if not last candle of clock
            if i < len(dtlist) - 1:
                enddt = dtlist[i + 1]
            # if there is no data to align, just set nan values
            if last_idx < 0:
                res.append(val)
                continue

            # align data from slice to clock
            while True:
                if (last_idx >= len(slicedata['float'])
                        or last_idx >= len(slicedata['value'])):
                    # all candles from data consumed
                    break
                # current values from data
                c_float = slicedata['float'][last_idx]
                c_val = slicedata['value'][last_idx]
                # forward until start of clock candle is reached
                if c_float < startdt:
                    if c_val == c_val:
                        last_val = c_val
                    last_idx += 1
                    continue
                # current value belongs to next clock entry
                if enddt and c_float >= enddt:
                    break
                # set value here
                if fillgaps or c_val != c_val:
                    val = last_val
                elif c_val == c_val:
                    val = c_val
                last_val = val
                last_idx += 1

            res.append(val)
        return res

    """
    def _get_data_from_list(self, llist, clk, fill_gaps=False):
        '''
        Generates data based on given clock
        '''
        data = []
        c_idx = 0
        sc = None
        # go through all clock values and align given data to clock
        for c in clk:
            v = float('nan')
            sc_prev = None
            idx_prev = None
            # go through all values to align starting from last index
            for sc_idx in range(c_idx, len(llist)):
                sc = self.clk[sc_idx]
                if sc < c:
                    # src clck is smaller: strat -> data_n
                    if llist[sc_idx] == llist[sc_idx]:
                        v = llist[sc_idx]
                elif sc == c:
                    # src clk equals: data_n -> data_n
                    if v != v or llist[sc_idx] == llist[sc_idx]:
                        v = llist[sc_idx]
                    c_idx = sc_idx + 1
                    break
                elif sc > c:
                    # scr clk bigger: data_m -> data_n
                    if fill_gaps or (sc_prev and sc_prev < c):
                        # fill only when clk value switched
                        if sc_prev:
                            v = llist[idx_prev]
                            c_idx = idx_prev + 1
                        else:
                            v = llist[sc_idx]
                            c_idx = sc_idx
                    break
                # remember current value if not nan
                if llist[sc_idx] == llist[sc_idx]:
                    sc_prev = sc
                    idx_prev = sc_idx
            # put value for c - clk pos from src clock
            data.append(v)

        return data
    """


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
        if isinstance(obj, bt.AbstractDataBase):
            source_id = get_source_id(obj)
            for linealias in obj.getlinealiases():
                if linealias in ['datetime']:
                    continue
                line = getattr(obj, linealias)
                slicedata = tmpclk.get_slice(
                    line, slice_startdt, slice_enddt)
                data = self._align_slice(
                    slicedata, startidx, endidx, fillgaps=fillgaps)
                df[source_id + linealias] = data
        else:
            for lineidx, line in enumerate(obj.lines):
                source_id = get_source_id(line)
                slicedata = tmpclk.get_slice(
                    line, slice_startdt, slice_enddt)
                data = self._align_slice(
                    slicedata, startidx, endidx, fillgaps=fillgaps)
                df[source_id] = data
        return df
