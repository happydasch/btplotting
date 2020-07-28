from collections import defaultdict

import numpy as np
import pandas as pd

from bokeh.models import ColumnDataSource


class CDSObject:

    '''
    Base class for FigurePage and Figure with ColumnDataSource support
    also alows to create custom columns which are not available in
    provided data.
    It will create data for stream, patch and set up the columns
    in ColumnDataSource

    It is using index and datetime columns as special cases:

    -index is added, so stream has also the real index of the row
     without it, the index would be resetted in ColumnDataSource
    -datetime is added only if there are any rows to prevent gaps
     in data, so this column should only be set in cds_cols if all
     values needs to be added

    This special cases will be available in every row
    '''

    def __init__(self, cols=[]):
        self._cds_cols = []
        self._cds_cols_default = cols
        self._cds = ColumnDataSource()
        self.set_cds_col(cols)

    @property
    def cds(self):
        '''
        Property for ColumnDataSource
        '''
        return self._cds

    @property
    def cds_cols(self):
        '''
        Property for Columns in ColumnDataSource
        '''
        return self._cds_cols

    def _get_cds_cols(self):
        '''
        Returns all set columns
        2 lissts will be returned:
        - columns: columns from data source
        - additional: additional data sources which should be
          created from data source
        '''
        columns = []
        additional = []
        for c in self._cds_cols:
            if isinstance(c, str):
                columns.append(c)
            else:
                additional.append(c)
        return columns, additional

    def _create_cds_col_from_df(self, op, df):
        '''
        Creates a column from DataFrame
        op - tuple: [0] - name of column
                    [1] - source column
                    [2] - other column or value
                    [3] - op method (callable with 2 params: a, b)
        '''
        a = np.array(df[op[1]])
        if isinstance(op[2], str):
            b = np.array(df[op[2]])
        else:
            b = np.full(df.shape[0], df[op[2]])
        arr = op[3](a, b)
        return arr

    def _create_cds_col_from_series(self, op, series):
        '''
        Creates a column from Series
        '''
        arr = self._create_cds_col_from_df(op, pd.DataFrame([series]))
        return arr[0]

    def set_cds_col(self, col):
        '''
        Sets ColumnDataSource columns to use
        allowed column types are string, tuple
        col can contain multiple columns in a list
        tuples will be used to create a new column from
        existing columns
        '''
        if not isinstance(col, list):
            col = [col]
        for c in col:
            if isinstance(c, str):
                if c not in self._cds_cols:
                    self._cds_cols.append(c)
            elif isinstance(c, tuple) and len(c) == 4:
                self._cds_cols.append(c)
            else:
                raise Exception("Unsupported col provided")

    def set_cds_columns_from_df(self, df, dropna=True):
        '''
        Sets the ColumnDataSource columns based on the given DataFrame using
        the given columns. Only the given columns will be added, all will be
        added if columns=None
        '''
        columns, additional = self._get_cds_cols()
        if not len(columns) > 0:
            columns = list(df.columns)
        try:
            c_df = df.loc[:, columns]
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
                # skip index and datetime since these are special
                # cases. they will be added later with the correct
                # dtype
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
        # add additional columns
        for a in additional:
            col = self._create_cds_col_from_df(a, c_df)
            self._cds.add(col, a[0])

    def get_cds_streamdata_from_df(self, df):
        '''
        Creates stream data from a pandas DataFrame
        '''
        columns, additional = self._get_cds_cols()
        if not len(columns) > 0:
            columns = list(df.columns)
        try:
            c_df = df.loc[:, columns]
        except Exception:
            return {}
        # use text NaN for nan values
        c_df.fillna('NaN')
        # ensure c_df contains index and datetime
        if 'index' not in c_df.columns:
            c_df.index = df.loc[c_df.index, 'index']
        if 'datetime' not in c_df.columns:
            c_df['datetime'] = df.loc[c_df.index, 'datetime']
        # add additional columns
        for a in additional:
            col = self._create_cds_col_from_df(a, c_df)
            c_df[a[0]] = col
        return ColumnDataSource.from_df(c_df)

    def get_cds_patchdata_from_series(self, series):
        '''
        Creates patch data from a pandas Series
        '''
        p_data = defaultdict(list)
        s_data = defaultdict(list)
        columns, additional = self._get_cds_cols()
        idx_map = {d: idx for idx, d in enumerate(self._cds.data['index'])}
        # get the index in cds for series index
        if series['index'] in idx_map:
            idx = idx_map[series['index']]
        else:
            idx = False
        # create patch or stream data based on given series
        if idx is not False:
            # ensure datetime is checked for changes
            if 'datetime' not in columns:
                columns.append('datetime')
            for c in columns:
                try:
                    val = series[c]
                    cds_val = self._cds.data[c][idx]
                    if (val == val and val != cds_val):
                        p_data[c].append((idx, val))
                except Exception:
                    continue
            for a in additional:
                c = a[0]
                cds_val = self._cds.data[c][idx]
                val = self._create_cds_col_from_series(a, series)
                if cds_val != val:
                    p_data[c].append((idx, val))
        else:
            # add all columns to stream result. This may be needed if a value
            # was nan and therefore not added before
            s_data = self.get_cds_streamdata_from_df(pd.DataFrame([series]))
        return p_data, s_data

    def cds_reset(self):
        '''
        Resets the ColumnDataSource and other config to default
        '''
        self._cds = ColumnDataSource()
        self._cds_cols = []
        self.set_cds_col(self._cds_cols_default)
