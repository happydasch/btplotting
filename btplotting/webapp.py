from datetime import datetime

from bokeh.application.handlers.function import FunctionHandler
from bokeh.application import Application
from bokeh.document import Document
from bokeh.server.server import Server
from bokeh.io import show
from bokeh.util.browser import view
from bokeh.server.views.ws import WSHandler
from jinja2 import Environment, PackageLoader

from .helper.bokeh import generate_stylesheet


def check_origin_overwrite(self, origin):
    return True


class Webapp:
    def __init__(self, title, html_template, scheme, model_factory_fnc,
                 on_session_destroyed=None, address="localhost", port=81,
                 autostart=False, iplot=True):
        self._title = title
        self._html_template = html_template
        self._scheme = scheme
        self._model_factory_fnc = model_factory_fnc
        self._on_session_destroyed = on_session_destroyed
        self._address = address
        self._port = port
        self._autostart = autostart
        self._iplot = iplot

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
                         port=self._port, autostart=self._autostart,
                         iplot=self._iplot)

    @staticmethod
    def _run_server(fnc_make_document, ioloop=None, address='localhost',
                    port=81, autostart=False, iplot=True):
        '''
        Runs a Bokeh webserver application. Documents will be created using
        fnc_make_document
        '''
        handler = FunctionHandler(fnc_make_document)
        app = Application(handler)

        if iplot:
            try:
                # src: https://stackoverflow.com/questions/44100477/how-to-check-if-you-are-in-a-jupyter-notebook
                get_ipython  # noqa: *
                # patch ws handler as a workaround for jupyter in vscode
                # check_origin will return allways true
                WSHandler.check_origin_src = WSHandler.check_origin
                WSHandler.check_origin = check_origin_overwrite
                return show(app)
            except NameError:
                pass

        apps = {'/': app}
        display_address = address if address != '*' else 'localhost'
        origin = [f'{address}:{port}' if address != '*' else address]
        server = Server(apps, port=port, io_loop=ioloop,
                        allow_websocket_origin=origin)
        if autostart:
            print('Browser is launching at'
                  f' http://{display_address}:{port}')
            view(f'http://{display_address}:{port}')
        else:
            print(f'Open browser at http://{display_address}:{port}')
        if ioloop is None:
            server.run_until_shutdown()
        else:
            server.start()
            ioloop.start()
