import logging
from tornado import gen

import pandas as pd

from ..clock import DataClockHandler

_logger = logging.getLogger(__name__)


class LiveDataHandler:

    '''
    Handler for live data
    '''

    def __init__(self, client):
        self._client = client
        self._datastore = None
        self._lastidx = -1
        self._patches = {}
        self._cb = None
        # inital fill of datastore
        self._fill()

    @gen.coroutine
    def _cb_push(self):
        '''
        Pushes to all ColumnDataSources
        '''
        fp = self._client.get_figurepage()

        # get all rows to patch
        patches = {}
        for idx in list(self._patches.keys()):
            try:
                patch = self._patches.pop(idx)
                patches[idx] = patch
            except KeyError:
                continue

        # patch figurepage
        for idx, patch in patches.items():
            p_data, s_data = fp.get_cds_patchdata_from_series(idx, patch)
            if len(p_data) > 0:
                _logger.debug(f'Sending patch for figurepage: {p_data}')
                fp.cds.patch(p_data)
            if len(s_data) > 0:
                _logger.debug(f'Sending stream for figurepage: {s_data}')
                fp.cds.stream(s_data, self._get_data_stream_length())
            # patch all figures
            for f in fp.figures:
                # only fill with nan if not filling gaps
                fillnan = f.fillnan()
                # get patch data
                p_data, s_data = f.get_cds_patchdata_from_series(
                    idx, patch, fillnan)
                if len(p_data) > 0:
                    _logger.debug(f'Sending patch for figure: {p_data}')
                    f.cds.patch(p_data)
                if len(s_data) > 0:
                    _logger.debug(f'Sending stream for figure: {s_data}')
                    f.cds.stream(s_data, self._get_data_stream_length())
                    self._lastidx = s_data['index'][-1]

        '''
        # take all rows from datastore that were not yet streamed
        update_df = self._datastore[self._datastore.index >= self._lastidx]
        if not update_df.shape[0]:
            return

        # store last index of streamed data
        self._lastidx = update_df.index[-1]

        # create stream data for figurepage
        data = fp.get_cds_streamdata_from_df(update_df)
        if data:
            _logger.debug(f'Sending stream for figurepage: {data}')
            fp.cds.stream(data, self._get_data_stream_length())

        # create stream df for every figure
        for f in fp.figures:
            data = f.get_cds_streamdata_from_df(update_df)
            if data:
                _logger.debug(f'Sending stream for figure: {data}')
                f.cds.stream(data, self._get_data_stream_length())
        self._lastidx = self._datastore.index[-1]
        '''

    def _fill(self):
        '''
        Fills datastore with latest values
        '''
        app = self._client.get_app()
        fp = self._client.get_figurepage()
        figid = self._client.get_figid()
        lookback = self._client.lookback
        df = app.get_data(figid=figid, back=lookback)
        self._set_data(df)
        # init by calling set_cds_columns_from_df
        # after this, all cds will already contain data
        fp.set_cds_columns_from_df(self._datastore)

    def _set_data(self, data, idx=None):
        '''
        Replaces or appends data to datastore
        '''
        if isinstance(data, pd.DataFrame):
            self._datastore = data
            self._lastidx = -1
        elif isinstance(data, pd.Series):
            if idx is None:
                self._datastore = self._datastore.append(data)
            else:
                self._datastore.loc[idx] = data
        else:
            raise Exception('Unsupported data provided')
        self._datastore = self._datastore.tail(
            self._get_data_stream_length())

    def _push(self):
        doc = self._client.get_doc()
        try:
            doc.remove_next_tick_callback(self._cb)
        except ValueError:
            pass
        self._cb = doc.add_next_tick_callback(self._cb_push)

    def _process_data(self, data):
        '''
        Request to update data with given data
        '''
        for idx, row in data.iterrows():
            if (idx in self._datastore.index):
                self._set_data(row, idx)
                self._patches[idx] = row
            else:
                self._set_data(row)

        # if self._datastore is not None:
        #     self._datastore.drop_duplicates("datetime", keep='last', inplace=True) 

        self._push()

    def _get_data_stream_length(self):
        '''
        Returns the length of data stream to use
        '''
        return min(self._client.lookback, self._datastore.shape[0])

    def get_last_idx(self):
        '''
        Returns the last index in local datastore
        '''
        if self._datastore.shape[0] > 0:
            return self._datastore.index[-1]
        return -1

    def set_df(self, df):
        '''
        Sets a new df and streams data
        '''
        self._set_data(df)
        self._push()

    def update(self):
        data = None
        # fp = self._client.get_figurepage()
        app = self._client.get_app()
        figid = self._client.get_figid()
        lookback = self._client.lookback
        # data_clock: DataClockHandler = fp.data_clock
        # clk = data_clock._get_clk()
        lastidx = self._lastidx
        lastavailidx = app.get_last_idx(figid)
        # if there is more new data then lookback length
        # don't load from last index but from end of data
        if (lastidx < 0 or lastavailidx - lastidx > (2 * lookback)):
            data = app.get_data(back=lookback)
        # if there is just some new data (less then lookback)
        # load from last index, so no data is skipped
        elif lastidx <= lastavailidx:
            startidx = max(0, lastidx - 2)
            # start = data_clock.get_dt_at_idx(startidx)
            data = app.get_data(startidx=startidx)
        # if any new data was loaded
        if data is not None:
            self._process_data(data)

    def stop(self):
        '''
        Stops the datahandler
        '''
        # ensure no pending calls are set
        doc = self._client.get_doc()
        try:
            doc.remove_next_tick_callback(self._cb)
        except ValueError:
            pass
