import logging
from threading import Lock
from functools import partial
from tornado import gen

from bokeh.io import curdoc
from bokeh.models import DataTable, TableColumn, ColumnDataSource, Div
from bokeh.layouts import column

from ..tab import BacktraderPlottingTab

handler = None


def init_log_tab(names, level=logging.NOTSET):
    global handler
    if handler is None:
        handler = CDSHandler(level=level)
        for n in names:
            logging.getLogger(n).addHandler(handler)


def is_log_tab_initialized():
    global handler
    return handler is not None


class CDSHandler(logging.Handler):

    def __init__(self, level=logging.NOTSET):
        super(CDSHandler, self).__init__(level=level)
        self._lock = Lock()
        self.messages = []
        self.idx = {}
        self.cds = {}
        self.cb = {}

    def emit(self, record):
        message = record.msg
        self.messages.append(message)
        with self._lock:
            for doc in self.cds:
                try:
                    doc.remove_next_tick_callback(self.cb[doc])
                except ValueError:
                    pass
                self.cb[doc] = doc.add_next_tick_callback(
                    partial(self._stream_to_cds, doc))

    def get_cds(self, doc):
        if doc not in self.cds:
            with self._lock:
                self.cds[doc] = ColumnDataSource(
                    data=dict(message=self.messages.copy()))
                self.cb[doc] = None
                self.idx[doc] = len(self.messages) - 1
                self.cds[doc].selected.indices = [self.idx[doc]]
        return self.cds[doc]

    @gen.coroutine
    def _stream_to_cds(self, doc):
        last = len(self.messages) - 1
        messages = self.messages[self.idx[doc] + 1:last + 1]
        if not len(messages):
            return
        with self._lock:
            self.idx[doc] = last
            self.cds[doc].stream({'message': messages})
            # move only to last if there is a selected row
            # when no row is selected, then don't move to new
            # row
            if len(self.cds[doc].selected.indices) > 0:
                self.cds[doc].selected.indices = [self.idx[doc]]


class LogTab(BacktraderPlottingTab):

    def _is_useable(self):
        return is_log_tab_initialized()

    def _get_tab_panel(self):
        global handler

        if handler is None:
            init_log_tab([])
        if self._client is not None:
            doc = self._client.get_doc()
        else:
            doc = curdoc()

        message = TableColumn(
            field='message',
            title='Message',
            sortable=False)
        title = Div(
            text='Log Messages',
            css_classes=['tab-panel-title'],
            stylesheets=[self._app.stylesheet])
        table = DataTable(
            source=handler.get_cds(doc),
            columns=[message],
            sizing_mode='stretch_width',
            scroll_to_selection=True,
            sortable=False,
            reorderable=False,
            fit_columns=True,
            stylesheets=[self._app.stylesheet])
        child = column(
            children=[title, table],
            sizing_mode='stretch_width')

        return child, 'Log'
