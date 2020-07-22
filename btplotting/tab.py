from bokeh.models.widgets import Panel


class BacktraderPlottingTab:

    '''
    Abstract class for tabs
    This class needs to be extended from when creating custom tabs.
    It is required to overwrite the _is_useable and _get_panel method.
    The _get_panel method needs to return a panel child and a title.
    '''

    def __init__(self, app, figurepage, client=None):
        self._app = app
        self._figurepage = figurepage
        self._client = client
        self._panel = None

    def _is_useable(self):
        raise Exception('_is_useable needs to be implemented.')

    def _get_panel(self):
        raise Exception('_get_panel needs to be implemented.')

    def is_useable(self):
        '''
        Returns if the tab is useable within the current environment
        '''
        return self._is_useable()

    def get_panel(self):
        '''
        Returns the panel to show as a tab
        '''
        child, title = self._get_panel()
        self._panel = Panel(child=child, title=title)
        return self._panel
