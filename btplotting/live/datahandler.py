import time
import logging
from enum import Enum
from threading import Thread, Lock
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

    def __init__(self, doc, app, figid, lookback, fill_gaps=True, timeout=1):
        # doc of client
        self._doc = doc
        # app instance
        self._app = app
        # figurepage id
        self._figid = figid
        # lookback length
        self._lookback = lookback
        # should gaps be filled
        self._fill_gaps = fill_gaps
        # timeout for thread
        self._timeout = timeout
        # figurepage
        self._figurepage = app.get_figurepage(figid)
        # thread to process new data
        self._thread = Thread(target=self._t_thread, daemon=True)
        self._lock = Lock()
        self._running = True
        self._new_data = False
        self._datastore = None
        self._last_idx = -1
        self._patches = []
        self._cb_patch = None
        self._cb_add = None
        # inital fill of datastore
        self._fill()
        # start thread
        self._thread.start()

    def _fill(self):
        '''
        Fills datastore with latest values
        '''
        df = self._app.generate_data(
            figid=self._figid,
            back=self._lookback,
            preserveidx=True,
            fill_gaps=self._fill_gaps)
        self._set_data(df)
        # init by calling set_cds_columns_from_df
        # after this, all cds will already contain data
        self._figurepage.set_cds_columns_from_df(self._datastore)

    def _set_data(self, data, idx=None):
        '''
        Replaces or appends data to datastore
        '''
        with self._lock:
            if isinstance(data, pd.DataFrame):
                self._datastore = data
                self._last_idx = -1
            elif isinstance(data, pd.Series):
                if idx is None:
                    self._datastore = self._datastore.append(data)
                else:
                    self._datastore.at[idx] = data
            else:
                raise Exception('Unsupported data provided')
            self._datastore = self._datastore.tail(
                self._get_data_stream_length())

    @gen.coroutine
    def _cb_push_adds(self):
        '''
        Streams new data to all ColumnDataSources
        '''

        # take all rows from datastore that were not yet streamed
        update_df = self._datastore[self._datastore['index'] > self._last_idx]
        # skip if we don't have new data
        if update_df.shape[0] == 0:
            return

        # store last index of streamed data
        self._last_idx = update_df['index'].iloc[-1]

        fp = self._figurepage
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

        for patch in patches:
            fp = self._figurepage

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
                if not self._fill_gaps:
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

    def _push_adds(self):
        doc = self._doc
        try:
            doc.remove_next_tick_callback(self._cb_add)
        except ValueError:
            pass
        self._cb_add = doc.add_next_tick_callback(
            self._cb_push_adds)

    def _push_patches(self):
        doc = self._doc
        try:
            doc.remove_next_tick_callback(self._cb_patch)
        except ValueError:
            pass
        self._cb_patch = doc.add_next_tick_callback(
            self._cb_push_patches)

    def _process(self, rows):
        '''
        Request to update data with given rows
        '''
        for idx, row in rows.iterrows():
            if (self._datastore.shape[0] > 0
                    and idx in self._datastore['index']):
                update_type = UpdateType.UPDATE
            else:
                update_type = UpdateType.ADD

            if update_type == UpdateType.UPDATE:
                ds_idx = self._datastore.loc[
                    self._datastore['index'] == idx].index[0]
                self._set_data(row, ds_idx)
                self._patches.append(row)
                self._push_patches()
            else:
                # append data and remove old data
                self._set_data(row)
                self._push_adds()

    def _t_thread(self):
        '''
        Thread method for datahandler
        '''
        while self._running:
            if self._new_data:
                last_idx = self.get_last_idx()
                last_avail_idx = self._app.get_last_idx(self._figid)
                if last_avail_idx - last_idx > (2 * self._lookback):
                    # if there is more new data then lookback length
                    # don't load from last index but from end of data
                    data = self._app.generate_data(
                        back=self._lookback,
                        preserveidx=True,
                        fill_gaps=self._fill_gaps)
                else:
                    # if there is just some new data (less then lookback)
                    # load from last index, so no data is skipped
                    data = self._app.generate_data(
                        start=last_idx,
                        preserveidx=True,
                        fill_gaps=self._fill_gaps)
                self._new_data = False
                self._process(data)
            time.sleep(self._timeout)

    def _get_data_stream_length(self):
        '''
        Returns the length of data stream to use
        '''
        return min(self._lookback, self._datastore.shape[0])

    def get_last_idx(self):
        '''
        Returns the last index in local datastore
        '''
        if self._datastore.shape[0] > 0:
            return self._datastore['index'].iloc[-1]
        return -1

    def set(self, df):
        '''
        Sets a new df and streams data
        '''
        self._set_data(df)
        self._push_adds()

    def update(self):
        '''
        Notifies datahandler of new data
        '''
        if self._running:
            self._new_data = True

    def stop(self):
        '''
        Stops the datahandler
        '''
        # mark as not running
        self._running = False
        # ensure no pending calls are set
        try:
            self._doc.remove_next_tick_callback(self._cb_patch)
        except ValueError:
            pass
        try:
            self._doc.remove_next_tick_callback(self._cb_add)
        except ValueError:
            pass
        # it would not really be neccessary to join this thread but doing
        # it for readability
        self._thread.join(0)
