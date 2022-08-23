import logging
from enum import Enum
from tornado import gen

import pandas as pd

_logger = logging.getLogger(__name__)


class UpdateType(Enum):
    ADD = 1,
    UPDATE = 2,


class LiveDataHandler:

    '''
    Handler for live data
    '''

    def __init__(self, client):
        self._client = client
        self._datastore = None
        self._lastidx = None
        self._patches = []
        self._cb_patch = None
        self._cb_add = None
        # inital fill of datastore
        self._fill()

    @gen.coroutine
    def _cb_push_adds(self):
        '''
        Streams new data to all ColumnDataSources
        '''

        # take all rows from datastore that were not yet streamed
        update_df = self._datastore[self._datastore.index > self._lastidx]
        # skip if we don't have new data
        if update_df.shape[0] == 0:
            return

        # store last index of streamed data
        self._lastidx = update_df.index[-1]

        fp = self._client.get_figurepage()
        # create stream data for figurepage
        data = fp.get_cds_streamdata_from_df(update_df)
        if data:
            _logger.debug(f'Sending stream for figurepage: {data}')
            fp.cds.stream(
                data, self._get_data_stream_length())

        # create stream df for every figure
        for f in fp.figures:
            data = f.get_cds_streamdata_from_df(update_df)
            if data:
                _logger.debug(f'Sending stream for figure: {data}')
                f.cds.stream(data, self._get_data_stream_length())

    @gen.coroutine
    def _cb_push_patches(self):
        '''
        Pushes patches to all ColumnDataSources
        '''
        # get all rows to patch
        patches = []
        while len(self._patches) > 0:
            patches.append(self._patches.pop(0))
        # skip if no patches available
        if len(patches) == 0:
            return

        fp = self._client.get_figurepage()
        fillgaps = self._client.fillgaps
        for patch in patches:
            # patch figurepage
            p_data, s_data = fp.get_cds_patchdata_from_series(patch)
            if len(p_data) > 0:
                _logger.debug(f'Sending patch for figurepage: {p_data}')
                fp.cds.patch(p_data)
            if len(s_data) > 0:
                _logger.debug(f'Sending stream for figurepage: {s_data}')
                fp.cds.stream(
                    s_data, self._get_data_stream_length())

            # patch all figures
            for f in fp.figures:
                # only fill with nan if not filling gaps
                if not fillgaps:
                    c_fill_nan = f.fill_nan()
                else:
                    c_fill_nan = []
                # get patch data
                p_data, s_data = f.get_cds_patchdata_from_series(
                    patch, c_fill_nan)
                if len(p_data) > 0:
                    _logger.debug(f'Sending patch for figure: {p_data}')
                    f.cds.patch(p_data)
                if len(s_data) > 0:
                    _logger.debug(f'Sending stream for figure: {s_data}')
                    f.cds.stream(
                        s_data, self._get_data_stream_length())

    def _fill(self):
        '''
        Fills datastore with latest values
        '''
        app = self._client.get_app()
        fp = self._client.get_figurepage()
        figid = self._client.get_figid()
        lookback = self._client.lookback
        fillgaps = self._client.fillgaps
        df = app.get_data(
            figid=figid, back=lookback, fillgaps=fillgaps, preserveidx=True)
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

    def _push_adds(self):
        doc = self._client.get_doc()
        try:
            doc.remove_next_tick_callback(self._cb_add)
            self._cb_add = doc.add_next_tick_callback(
                self._cb_push_adds)
        except ValueError:
            pass

    def _push_patches(self):
        doc = self._client.get_doc()
        try:
            doc.remove_next_tick_callback(self._cb_patch)
            self._cb_patch = doc.add_next_tick_callback(
                self._cb_push_patches)
        except ValueError:
            pass

    def _process_data(self, data):
        '''
        Request to update data with given data
        '''
        # TODO append df to datastore
        for idx, row in data.iterrows():
            if (self._datastore.shape[0] > 0
                    and idx in self._datastore.index):
                update_type = UpdateType.UPDATE
            else:
                update_type = UpdateType.ADD

            if update_type == UpdateType.UPDATE:
                ds_idx = self._datastore.loc[
                    self._datastore.index == idx].index[0]
                self._set_data(row, ds_idx)
                self._patches.append(row)
                self._push_patches()
            else:
                # append data and remove old data
                self._set_data(row)
                self._push_adds()

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
        self._push_adds()

    def update(self):
        fp = self._client.get_figurepage()
        app = self._client.get_app()
        figid = self._client.get_figid()
        lookback = self._client.lookback
        fillgaps = self._client.fillgaps
        data_clock = fp.data_clock
        last_idx = self.get_last_idx()
        last_avail_idx = app.get_last_idx(figid)
        data = None
        idx = max(0, last_avail_idx - lookback)
        start = data_clock.get_dt_at_idx(idx)
        # if there is more new data then lookback length
        # don't load from last index but from end of data
        if (start == start
            and (last_idx < 0
                 or last_avail_idx - last_idx > (2 * lookback))):
            data = app.get_data(
                start=start, fillgaps=fillgaps, preserveidx=True)
        # if there is just some new data (less then lookback)
        # load from last index, so no data is skipped
        elif last_idx < last_avail_idx:
            start = data_clock.get_dt_at_idx(self._lastidx)
            data = app.get_data(
                start=start, fillgaps=fillgaps, preserveidx=True)
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
            doc.remove_next_tick_callback(self._cb_patch)
        except ValueError:
            pass
        try:
            doc.remove_next_tick_callback(self._cb_add)
        except ValueError:
            pass
