from collections import defaultdict

import numpy as np
import pandas as pd

from bokeh.models import ColumnDataSource


class CDSObject:

    def __init__(self, cols=[]):
        self._cds_cols = []
        self._cds_cols_default = cols
        self._cds = ColumnDataSource()
        self.set_cds_col(cols)

    @property
    def cds(self):
        return self._cds

    @property
    def cds_cols(self):
        return self._cds_cols

    def set_cds_col(self, col):
        '''
        Sets ColumnDataSource columns to use
        '''
        if not isinstance(col, list):
            col = [col]
        for c in col:
            if isinstance(c, str) and c not in self._cds_cols:
                self._cds_cols.append(c)
            else:
                raise Exception("Unsupported col provided")

    def set_cds_columns_from_df(self, df, dropna=True):
        '''
        Sets the ColumnDataSource columns based on the given DataFrame using
        the given columns. Only the given columns will be added, all will be
        added if columns=None
        '''
        try:
            if len(self._cds_cols) > 0:
                c_df = df.loc[:, self._cds_cols]
            else:
                c_df = df.loc[:, df.columns]
        except Exception:
            return None
        # remove empty rows
        if dropna:
            c_df = c_df.dropna(how='all')
        # use text nan for nan values
        c_df.fillna('NaN')
        # add all columns and values
        for c in c_df:
            if c in ['index', 'datetime']:
                continue
            if c in self._cds.column_names:
                self._cds.remove(c)
            self._cds.add(np.array(c_df.loc[:, c]), c)
        # ensure cds contains index
        if 'index' in self._cds.column_names:
            self._cds.remove('index')
        self._cds.add(
            np.array(df.loc[c_df.index, 'index'], dtype=np.int64),
            'index')
        # ensure cds contains corresponding datetime entries
        if 'datetime' in self._cds.column_names:
            self._cds.remove('datetime')
        self._cds.add(
            np.array(df.loc[c_df.index, 'datetime'], dtype=np.datetime64),
            'datetime')

    def get_cds_streamdata_from_df(self, df):
        '''
        Creates stream data from a pandas DataFrame
        '''
        try:
            if len(self._cds_cols) > 0:
                c_df = df.loc[:, self._cds_cols]
            else:
                c_df = df.loc[:, df.columns]
        except Exception:
            return None
        # use text NaN for nan values
        c_df.fillna('NaN')
        # ensure c_df contains index
        if 'index' not in c_df.columns:
            c_df.index = df.loc[c_df.index, 'index']
        # ensure c_df contains corresponding datetime entries
        if 'datetime' not in c_df.columns:
            c_df['datetime'] = df.loc[c_df.index, 'datetime']
        return ColumnDataSource.from_df(c_df)

    def get_cds_patchdata_from_series(self, series):
        '''
        Creates patch data from a pandas Series
        '''
        p_data = defaultdict(list)
        s_data = defaultdict(list)
        idx_map = {d: idx for idx, d in enumerate(self._cds.data['index'])}
        # get the index in cds for series index
        if series['index'] in idx_map:
            idx = idx_map[series['index']]
        else:
            idx = False
        # create patch or stream data based on given series
        if idx is not False:
            for c in series.axes[0]:
                if c not in self._cds.data:
                    continue
                val = series[c]
                cds_val = self._cds.data[c][idx]
                if (val == val and val != cds_val):
                    p_data[c].append((idx, val))
            # ensure datetime is always patched
            if 'datetime' not in p_data:
                p_data['datetime'].append((idx, series['datetime']))
        else:
            # add all columns to stream result. This may be needed if a value
            # was nan and therefore not added before
            for c in self._cds.column_names:
                val = series[c] if not pd.isna(series[c]) else 'NaN'
                s_data[c].append(val)
        return p_data, s_data

    def cds_reset(self):
        '''
        Resets the ColumnDataSource and other config to default
        '''
        self._cds = ColumnDataSource()
        self._cds_cols = []
        self.set_cds_col(self._cds_cols_default)
