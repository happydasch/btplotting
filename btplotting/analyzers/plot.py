import asyncio
import logging
from threading import Thread, Lock

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
        ('address', 'localhost'),
        ('port', 80),
        ('title', None),
        ('interval', 0.2),
        ('paused_at_beginning', False),
    )

    def __init__(self, iplot=True, autostart=False, **kwargs):
        title = self.p.title
        if title is None:
            title = 'Live %s' % type(self.strategy).__name__
        self._title = title
        self._webapp = Webapp(
            self._title,
            'basic.html.j2',
            self.p.scheme,
            self._app_cb_build_root_model,
            on_session_destroyed=self._on_session_destroyed,
            address=self.p.address,
            port=self.p.port,
            autostart=autostart,
            iplot=iplot)
        self._lock = Lock()
        self._clients = {}
        self._app_kwargs = kwargs

    def _create_app(self):
        return BacktraderPlotting(
            style=self.p.style,
            scheme=self.p.scheme,
            **self._app_kwargs)

    def _on_session_destroyed(self, session_context):
        with self._lock:
            self._clients[session_context.id].stop()
            del self._clients[session_context.id]

    def _t_server(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = tornado.ioloop.IOLoop.current()
        self._webapp.start(loop)

    def _app_cb_build_root_model(self, doc):
        client = LiveClient(doc,
                            self._create_app(),
                            self.strategy,
                            self.p.lookback,
                            self.p.paused_at_beginning,
                            self.p.interval)
        with self._lock:
            self._clients[doc.session_context.id] = client
        return client.model

    def start(self):
        '''
        Start from backtrader
        '''
        _logger.debug('Starting PlotListener...')
        t = Thread(target=self._t_server)
        t.daemon = True
        t.start()

    def stop(self):
        '''
        Stop from backtrader
        '''
        _logger.debug('Stopping PlotListener...')
        for c in list(self._clients.values()):
            c.stop()

    def next(self):
        '''
        Next from backtrader, new data arrives
        '''
        for c in list(self._clients.values()):
            c.next()
