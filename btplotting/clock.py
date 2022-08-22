import bisect

from datetime import datetime

import pandas as pd
import backtrader as bt

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
            10:08 10:09, 10:10, 10:11
            data entries:
            10:00, 10:05, 10:10

            will result in:
            index   clock   aligned data    fillgaps
            1       10:00   10:00           10:00
            2       10:01   nan             10:00
            3       10:02   nan             10:00
            4       10:03   nan             10:00
            5       10:04   nan             10:00
            6       10:05   10:05           10:05
            7       10:06   nan             10:05
            8       10:07   nan             10:05
            9       10:08   nan             10:05
            10      10:09   nan             10:05
            11      10:10   10:10           10:10
            12      10:11   nan             10:10
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

    def _get_start_end_idx(
            self, start: datetime = None, end: datetime = None,
            back=None, alwaysreturn=False):
        '''
        Returns the start and end idx for a given datetime
        '''
        start_idx = (
            None
            if start is None
            else bisect.bisect_left(
                self._clk.array, bt.date2num(start, tz=self._tz)))
        if start_idx is not None and start_idx >= len(self):
            start_idx = None
        end_idx = (
            None
            if end is None
            else bisect.bisect_right(
                self._clk.array, bt.date2num(end, tz=self._tz)))
        if end_idx is not None and end_idx >= len(self):
            end_idx = None
        if back:
            if end_idx is None:
                end_idx = len(self) - 1
            start_idx = end_idx - back + 1
        if alwaysreturn and start_idx is None:
            start_idx = 0
        if alwaysreturn and end_idx is None:
            end_idx = len(self) - 1
        return start_idx, end_idx

    def _align_slice(self, slicedata, start: datetime = None,
                     end: datetime = None, back=None, fillgaps=False):
        '''
        Aligns a slice to the clock
        '''
        res = []
        last_idx = -1 if not len(slicedata['float']) else 0
        last_val = None
        dt_list = self.get_dt_list(start, end, back, asfloat=True)
        for i in range(0, len(dt_list)):
            aval = float('nan')
            # get the time range for current clock entry
            start_dt = dt_list[i]
            end_dt = None
            if i < len(dt_list) - 1:
                end_dt = dt_list[i + 1]
            if last_idx < 0:
                res.append(aval)
                continue
            while True:
                if last_idx >= len(slicedata['float']) or last_idx >= len(slicedata['value']):
                    # all consumed
                    break
                c_float = slicedata['float'][last_idx]
                c_val = slicedata['value'][last_idx]
                # forward until start dt is reached
                if c_float < start_dt:
                    if c_val == c_val:
                        last_val = c_val
                    last_idx += 1
                    continue
                # wait, current value belongs to next clock entry
                if end_dt and c_float >= end_dt:
                    break
                # set value
                # either last value if nan and fillgaps or current value
                if fillgaps and c_val != c_val:
                    aval = last_val
                elif c_val == c_val:
                    aval = c_val
                last_val = aval
                last_idx += 1

            res.append(aval)
        return res

    def get_dt_at_idx(self, idx, localized=True):
        return bt.num2date(
            self._clk.array[idx],
            tz=None if not localized else self._tz)

    def get_float_at_idx(self, idx):
        return self._clk.array[idx]

    def get_index_list(self, start: datetime = None, end: datetime = None,
                       back=None, preserveidx=False):
        '''
        Returns a list with int indexes for the clock
        '''
        start_idx, end_idx = self._get_start_end_idx(
            start, end, back, alwaysreturn=True)
        if preserveidx:
            return [int(x) for x in range(start_idx, end_idx + 1)]
        return [int(x) for x in range(end_idx - start_idx + 1)]

    def get_dt_list(self, start: datetime = None, end: datetime = None,
                    back=None, asfloat=False, localized=True):
        '''
        Returns a list with datetime/float indexes for the clock
        '''
        dt_list = []
        for i in self.get_index_list(start, end, back, True):
            val = self._clk.array[i]
            if not asfloat:
                val = bt.num2date(val, tz=None if not localized else self._tz)
            dt_list.append(val)
        return dt_list

    def get_slice(self, line, start: datetime = None, end: datetime = None,
                  back=None):
        '''
        Returns a slice from given line

        This method is used to slice something from another clock for later
        alignment in another clock.
        '''
        res = {'float': [], 'value': []}
        for i in self.get_index_list(start, end, back, True):
            res['float'].append(self._clk.array[i])
            res['value'].append(line.array[i])
        return res

    def get_data(self, obj, start: datetime = None, end: datetime = None,
                 back=None, fillgaps=False):
        start_idx, end_idx = self._get_start_end_idx(
            start, end, back, alwaysreturn=True)
        start_dt = (
            self.get_dt_at_idx(start_idx)
            if start_idx is not None
            else self.get_dt_at_idx(0))
        end_dt = (
            self.get_dt_at_idx(end_idx)
            if end_idx is not None
            else None)
        dataname = get_dataname(obj)
        tmpclk = DataClockHandler(self._strategy, dataname)
        df = pd.DataFrame()
        if isinstance(obj, bt.AbstractDataBase):
            source_id = get_source_id(obj)
            for linealias in obj.getlinealiases():
                if linealias in ['datetime']:
                    continue
                line = getattr(obj, linealias)
                slicedata = tmpclk.get_slice(line, start_dt, end_dt)
                data = self._align_slice(slicedata, start_dt, end_dt, fillgaps)
                df[source_id + linealias] = data
        else:
            for lineidx, line in enumerate(obj.lines):
                slicedata = tmpclk.get_slice(line, start_dt, end_dt)
                source_id = get_source_id(line)
                data = self._align_slice(slicedata, start_dt, end_dt, fillgaps)
                df[source_id] = data
        return df
