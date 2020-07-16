from enum import Enum
from threading import Lock
import logging
from tornado import gen

from ..helper.bokeh import get_streamdata_from_df, get_patchdata_from_series

_logger = logging.getLogger(__name__)


class UpdateType(Enum):
    ADD = 1,
    UPDATE = 2,


class LiveDataHandler:

    '''
    Handler for live data
    '''

    def __init__(self, client, lookback, datadomain):
        self._lock = Lock()
        self._client = client
        self._lookback = lookback
        self._datadomain = datadomain
        self._last_idx = -1
        self._datastore = None
        self._patches = []
        self._cb_patch = None
        self._cb_add = None
        # inital fill of datastore
        self._fill()

    def _fill(self):
        # fill datastore with latest values
        with self._lock:
            self._datastore = self._client.app.build_data(
                self._client.strategy,
                back=self._lookback,
                preserveidx=True,
                datadomain=self._client.datadomain)
            if self._datastore.shape[0] > 0:
                self._last_idx = self._datastore['index'].iloc[-1]
            # init figurepage and figure cds by calling set_data_from_df
            # after this, all cds will already contain data, so no need
            # to push adds
            self._client.figurepage.set_data_from_df(self._datastore)

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
        self._last_idx = self._datastore['index'].iloc[-1]

        figurepage = self._client.figurepage
        # create stream data for figurepage
        data = get_streamdata_from_df(
            update_df,
            figurepage.cds_cols)
        _logger.debug(f'Sending stream for figurepage: {data}')
        figurepage.cds.stream(data, self._datastore.shape[0])

        # create stream df for every figure
        for figure in figurepage.figures:
            data = get_streamdata_from_df(update_df, figure.cds_cols)
            _logger.debug(f'Sending stream for figure: {data}')
            figure.cds.stream(data, self._datastore.shape[0])

    @gen.coroutine
    def _cb_push_patches(self):
        '''
        Pushes patches to all ColumnDataSources
        '''

        # get all rows to patch
        patches = self._patches
        self._patches = []
        # skip if no patches available
        if len(patches) == 0:
            return

        for patch in patches:
            figurepage = self._client.figurepage

            # patch figurepage
            p_data, s_data = get_patchdata_from_series(
                patch, figurepage.cds, figurepage.cds_cols)
            if len(p_data) > 0:
                _logger.debug(f"Sending patch for figurepage: {p_data}")
                figurepage.cds.patch(p_data)
            if len(s_data) > 0:
                _logger.debug(f"Sending stream for figurepage: {s_data}")
                figurepage.cds.stream(s_data)

            # patch all figures
            for figure in figurepage.figures:
                p_data, s_data = get_patchdata_from_series(
                    patch, figure.cds, figure.cds_cols)
                if len(p_data) > 0:
                    _logger.debug(f"Sending patch for figure: {p_data}")
                    figure.cds.patch(p_data)
                if len(s_data) > 0:
                    _logger.debug(f"Sending stream for figure: {s_data}")
                    figure.cds.stream(s_data)

    def _push_adds(self):
        doc = self._client.doc
        try:
            doc.remove_next_tick_callback(self._cb_add)
        except ValueError:
            pass
        self._cb_add = doc.add_next_tick_callback(
            self._cb_push_adds)

    def _push_patches(self):
        doc = self._client.doc
        try:
            doc.remove_next_tick_callback(self._cb_patch)
        except ValueError:
            pass
        self._cb_patch = doc.add_next_tick_callback(
            self._cb_push_patches)

    def get_last_idx(self):
        if self._datastore.shape[0] > 0:
            return self._datastore['index'].iloc[-1]
        return -1

    def set(self, df):
        with self._lock:
            self._datastore = df
        self._last_idx = -1
        self._push_adds()

    def update(self, rows):
        '''
        Request to update data with given rows
        '''

        strategy = self._client.strategy
        datadomain = self._client.datadomain
        # don't do anything if datadomain is different than
        # what the client is showing
        if datadomain != self._datadomain:
            return

        for idx, row in rows.iterrows():
            if (self._datastore.shape[0] > 0
                    and idx in self._datastore['index']):
                update_type = UpdateType.UPDATE
            else:
                update_type = UpdateType.ADD

            if update_type == UpdateType.UPDATE:
                ds_idx = self._datastore.loc[
                    self._datastore['index'] == idx].index[0]
                with self._lock:
                    self._datastore.at[ds_idx] = row
                    self._patches.append(row)
                self._push_patches()
            else:
                # check for gaps in data before adding new data
                if (
                        self._last_idx > -1
                        and self._datastore.shape[0] > 0
                        and row['index']
                        > (self._datastore['index'].iloc[-1] + 1)):
                    missing = self._client.app.build_data(
                        strategy=strategy,
                        start=self._datastore['index'].iloc[-1],
                        datadomain=datadomain,
                        preserveidx=True)
                    # add missing rows
                    self.update(missing)
                    # if any gap occured, no need to continue, since
                    # current rows were already updated
                    return

                # append data and remove old data
                with self._lock:
                    self._datastore = self._datastore.append(row)
                    self._datastore = self._datastore.tail(self._lookback)
                self._push_adds()
