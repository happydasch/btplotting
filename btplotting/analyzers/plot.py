import asyncio
import logging
from threading import Lock
import threading

import backtrader as bt

import tornado.ioloop

from ..app import BacktraderPlotting
from ..webapp import Webapp
from ..schemes import Blackly
from ..live.client import LiveClient


_logger = logging.getLogger(__name__)


class LivePlotAnalyzer(bt.Analyzer):

    params = (
        ('scheme', Blackly()),
        ('style', 'bar'),
        ('lookback', 23),
        ('http_port', 80),
        ('title', None),
    )

    def __init__(self, **kwargs):
        title = self.p.title
        if title is None:
            title = "Live %s" % type(self.strategy).__name__
        self._webapp = Webapp(
            title,
            'basic.html.j2',
            self.p.scheme,
            self._app_cb_build_root_model,
            on_session_destroyed=self._on_session_destroyed,
            port=self.p.http_port)
        self._lock = Lock()
        self._clients = {}
        self._app_kwargs = kwargs
        self._app = self._create_app()

    def _create_app(self):
        return BacktraderPlotting(
            style=self.p.style,
            scheme=self.p.scheme,
            **self._app_kwargs)

    def _on_session_destroyed(self, session_context):
        with self._lock:
            del self._clients[session_context.id]

    def _t_server(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = tornado.ioloop.IOLoop.current()
        self._webapp.start(loop)

    def _app_cb_build_root_model(self, doc):
        client = LiveClient(doc,
                            self._create_app,
                            self.strategy,
                            self.p.lookback)
        with self._lock:
            self._clients[doc.session_context.id] = client
        return client.model

    def start(self):
        _logger.debug("Starting PlotListener...")
        t = threading.Thread(target=self._t_server)
        t.daemon = True
        t.start()

    def stop(self):
        pass

    def next(self):
        rows = {}
        # don't run next while previous next is processing
        with self._lock:
            for c in self._clients.values():
                datadomain = c.datadomain
                if datadomain not in rows:
                    rows[datadomain] = self._app.build_data(
                        self.strategy,
                        back=2,
                        preserveidx=True,
                        datadomain=datadomain)
                c.update(rows[datadomain])
