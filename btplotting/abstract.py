import numpy as np

from bokeh.models import ColumnDataSource


class CDSObject:

    def __init__(self, cols=[]):
        self._cds_cols = []
        self._cds = ColumnDataSource()
        self.set_cds_col(cols)

    @property
    def cds(self):
        return self._cds

    @property
    def cds_cols(self):
        return self._cds_cols

    def set_cds_col(self, col):
        if isinstance(col, list):
            for c in col:
                self._cds_cols.append(c)
        elif isinstance(col, str):
            if col not in self._cds_cols:
                self._cds_cols.append(col)
        else:
            raise Exception("Unsupported col provided")

    def set_cds_columns_from_df(self, df, columns=None, dropna=True):
        '''
        Sets the ColumnDataSource columns based on the given DataFrame using
        the given columns. Only the given columns will be added, all will be
        added if columns=None
        '''
        c_df = df.loc[:, self._cds_cols]
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

    def cds_reset(self):
        self._cds = ColumnDataSource()
        self._cds_cols = []
