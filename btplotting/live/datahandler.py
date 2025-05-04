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
        fp = self._client.get_figurepage()

        _logger.debug(f"Starting _cb_push. Current datastore shape: {self._datastore.shape}")
        _logger.debug(f"Current datastore index: {self._datastore.index}")

        def log_cds_state(cds, message):
            lengths = {col: len(data) for col, data in cds.data.items()}
            _logger.debug(f"{message} - CDS lengths: {lengths}")
            if len(set(lengths.values())) > 1:
                _logger.warning(f"{message} - CDS columns have different lengths!")

        log_cds_state(fp.cds, "Initial state")

        patches = {idx: self._patches.pop(idx) for idx in list(self._patches.keys())}
        _logger.debug(f"Patches to apply: {len(patches)}")

        for idx, patch in patches.items():
            _logger.debug(f"Processing patch for index {idx}")
            p_data, s_data = fp.get_cds_patchdata_from_series(idx, patch)
            
            if p_data:
                _logger.debug(f"Patch data for index {idx}: {p_data}")
                fp.cds.patch(p_data)
                log_cds_state(fp.cds, f"After patching index {idx}")
            
            if s_data:
                _logger.debug(f"Stream data for index {idx}: {s_data}")
                fp.cds.stream(s_data, self._get_data_stream_length())
                log_cds_state(fp.cds, f"After streaming index {idx}")
            
            for f in fp.figures:
                fillnan = f.fillnan()
                p_data, s_data = f.get_cds_patchdata_from_series(idx, patch, fillnan)
                
                if p_data:
                    _logger.debug(f"Figure patch data for index {idx}: {p_data}")
                    f.cds.patch(p_data)
                    log_cds_state(f.cds, f"After patching figure for index {idx}")
                
                if s_data:
                    _logger.debug(f"Figure stream data for index {idx}: {s_data}")
                    f.cds.stream(s_data, self._get_data_stream_length())
                    log_cds_state(f.cds, f"After streaming figure for index {idx}")
                    self._lastidx = s_data['index'][-1] if 'index' in s_data else self._lastidx

        update_df = self._datastore[self._datastore.index > self._lastidx]
        _logger.debug(f"Rows to update: {update_df.shape[0]}")

        if not update_df.empty:
            self._lastidx = update_df.index[-1]
            data = fp.get_cds_streamdata_from_df(update_df)
            if data:
                _logger.debug(f"Streaming data from update_df: {data}")
                fp.cds.stream(data, self._get_data_stream_length())
                log_cds_state(fp.cds, "After streaming update_df")

            for f in fp.figures:
                data = f.get_cds_streamdata_from_df(update_df)
                if data:
                    _logger.debug(f"Streaming figure data from update_df: {data}")
                    f.cds.stream(data, self._get_data_stream_length())
                    log_cds_state(f.cds, "After streaming figure update_df")

        _logger.debug(f"Final datastore shape: {self._datastore.shape}")
        _logger.debug(f"Final datastore index: {self._datastore.index}")
        log_cds_state(fp.cds, "Final state")

        _logger.debug("Finished _cb_push")
    

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
        _logger.debug(f"Setting data. Type: {type(data)}, idx: {idx}")
        if isinstance(data, pd.DataFrame):
            self._datastore = data
            self._lastidx = -1
        elif isinstance(data, pd.Series):
            if idx is None:
                self._datastore = pd.concat([self._datastore, pd.DataFrame(data).T])
            else:
                self._datastore.loc[idx] = data
        else:
            raise Exception('Unsupported data provided')

        self._datastore = self._datastore.tail(self._get_data_stream_length())
        self._datastore = self._datastore.reset_index(drop=True)
        _logger.debug(f"Datastore after setting data: {self._datastore.shape}")
        _logger.debug(f"Datastore index after setting data: {self._datastore.index}")



    def _push(self):
        doc = self._client.get_doc()
        try:
            doc.remove_next_tick_callback(self._cb)
        except ValueError:
            pass
        self._cb = doc.add_next_tick_callback(self._cb_push)

    def _process_data(self, data):
        _logger.debug(f"Starting _process_data. Data shape: {data.shape}")
        _logger.debug(f"Data index: {data.index}")

        for idx, row in data.iterrows():
            _logger.debug(f"Processing row with index {idx}")
            if idx in self._datastore.index:
                _logger.debug(f"Updating existing row at index {idx}")
                self._set_data(row, idx)
                self._patches[idx] = row
            else:
                _logger.debug(f"Adding new row at index {idx}")
                self._set_data(row)

        if self._datastore is not None:
            _logger.debug(f"Datastore before cleanup: {self._datastore.shape}")
            self._datastore = self._datastore.drop_duplicates("datetime", keep='last')
            self._datastore = self._datastore.reset_index(drop=True)
            _logger.debug(f"Datastore after cleanup: {self._datastore.shape}")
            _logger.debug(f"Datastore index after cleanup: {self._datastore.index}")

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
