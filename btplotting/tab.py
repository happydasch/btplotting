from bokeh.models.widgets import Panel


class BacktraderPlottingTab:

    def __init__(self, app, figurepage, client=None):
        self.app = app
        self.figurepage = figurepage
        self.client = client
        self.panel = None

    def _is_useable(self):
        raise Exception("_is_useable needs to be implemented.")

    def _get_panel(self):
        raise Exception("_get_panel needs to be implemented.")

    def is_useable(self):
        return self._is_useable()

    def get_panel(self):
        child, title = self._get_panel()
        self.panel = Panel(child=child, title=title)
        return self.panel
