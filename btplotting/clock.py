import bisect

import pandas as pd
import backtrader as bt


class ClockGenerator:

    def __init__(self, clk, tz):
        self._clk = clk
        self._tz = tz

    def _get_clock_array(self):
        # parse only values, skip nan
        clk_arr = [bt.num2date(x, self._tz) for x in self._clk.array if x == x]
        return clk_arr

    def _get_clock_range(self, arr, start=None, end=None, back=None):

        """
        Returns the range (start, end + 1)
        """

        if start is None:
            start = 0
        elif type(start) == float:
            start = bisect.bisect_left(arr, bt.date2num(start))
        if end is None:
            end = len(arr) - 1
        elif type(end) == float:
            end = bisect.bisect_right(arr, bt.date2num(end))
        if end < 0:
            end = len(arr) + end
        # if back is provided, move back from end, override start
        if back:
            # prevent negative start int
            start = max(0, end - back)
        # increase end by 1, so when using it, the last entry is also
        # returned
        end += 1
        return start, end

    def get_clock_values(self, start=None, end=None, back=None):
        start, end = self._get_clock_range(
            self._clk.array, start, end, back)
        arr = self._get_clock_array()
        arr = arr[start:end]
        return arr, start, end


class ClockHandler:

    def __init__(self, clk, clkstart, clkend, parent_clk=None):
        self._clk = clk
        self._clkstart = clkstart
        self._clkend = clkend
        self._parent_clk = parent_clk

    def get_clock_array(self):
        return self._clk

    def get_list_from_line(self, line):
        arr = line.plotrange(self._clkstart, self._clkend)
        p_clk = self._parent_clk
        if p_clk is None:
            p_clk = self._clk
        # if there is a parent clock, align data to parent clock
        new_line = []
        c_idx = 0
        # sometimes clock is longer than line data
        c_len = min(len(self._clk), len(arr))
        sc_prev = None
        for sc in p_clk:
            if c_idx < c_len:
                v = self._clk[c_idx]
                if sc == v:
                    new_line.append(arr[c_idx])
                    c_idx += 1
                elif sc_prev and sc_prev < v and sc > v:
                    new_line.append(arr[c_idx])
                    c_idx += 1
                else:
                    new_line.append(float('nan'))
            else:
                new_line.append(float('nan'))
            sc_prev = sc
        return new_line

    def get_df_from_series(self, series, name_prefix=""):
        df = pd.DataFrame()
        for lineidx in range(series.size()):
            linealias = series.lines._getlinealias(lineidx)
            if linealias == 'datetime':
                continue
            line = series.lines[lineidx]
            df[name_prefix + linealias] = self.get_list_from_line(line)
        return df
