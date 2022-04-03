import sys

from datetime import datetime

from bokeh.application.handlers.function import FunctionHandler
from bokeh.application import Application
from bokeh.document import Document
from bokeh.server.server import Server
from bokeh.io import show
from bokeh.util.browser import view

from jinja2 import Environment, PackageLoader

from .helper.bokeh import generate_stylesheet


class Webapp:
    def __init__(self, title, html_template, scheme, model_factory_fnc,
                 on_session_destroyed=None, address="localhost", port=8889,
                 autostart=False):
        self._title = title
        self._html_template = html_template
        self._scheme = scheme
        self._model_factory_fnc = model_factory_fnc
        self._on_session_destroyed = on_session_destroyed
        self._address = address
        self._port = port
        self._autostart = autostart

    def start(self, ioloop=None):
        '''
        Serves a backtrader result as a Bokeh application running on
        a web server
        '''

        def make_document(doc: Document):
            if self._on_session_destroyed is not None:
                doc.on_session_destroyed(self._on_session_destroyed)

            # set document title
            doc.title = self._title

            # set document template
            now = datetime.now()
            env = Environment(loader=PackageLoader('btplotting', 'templates'))
            templ = env.get_template(self._html_template)
            templ.globals['now'] = now.strftime('%Y-%m-%d %H:%M:%S')
            doc.template = templ
            doc.template_variables['stylesheet'] = generate_stylesheet(
                self._scheme)
            model = self._model_factory_fnc(doc)
            doc.add_root(model)

        self._run_server(make_document, ioloop=ioloop, address=self._address,
                         port=self._port, autostart=self._autostart)

    @staticmethod
    def _run_server(fnc_make_document, notebook_url='localhost:8889',
                    iplot=True, ioloop=None, address='localhost', port=8889,
                    autostart=False):
        '''
        Runs a Bokeh webserver application. Documents will be created using
        fnc_make_document
        '''

        handler = FunctionHandler(fnc_make_document)
        app = Application(handler)

        ipython = iplot and 'ipykernel' in sys.modules
        if ipython:
            try:
                get_ipython
            except:
                ipython = False

        if ipython:
            show(app, notebook_url=notebook_url)  # noqa
        else:
            apps = {'/': app}
            display_address = address if address != '*' else 'localhost'
            if autostart:
                print(f'Browser is launching at http://{display_address}:{port}')
                view(f'http://{display_address}:{port}')
            else:
                print(f'Open browser at http://{display_address}:{port}')
            server = Server(apps, port=port, allow_websocket_origin=[address],
                            io_loop=ioloop)
            if ioloop is None:
                server.run_until_shutdown()
            else:
                server.start()
                ioloop.start()
