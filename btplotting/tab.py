from bokeh.models import TabPanel


class BacktraderPlottingTab:

    '''
    Abstract class for tabs
    This class needs to be extended from when creating custom tabs.
    It is required to overwrite the _is_useable and _get_tab_panel method.
    The _get_tab_panel method needs to return a tab panel child and a title.
    '''

    def __init__(self, app, figurepage, client=None):
        self._app = app
        self._figurepage = figurepage
        self._client = client
        self._tab_panel = None

    def _is_useable(self):
        raise Exception('_is_useable needs to be implemented.')

    def _get_tab_panel(self):
        raise Exception('_get_tab_panel needs to be implemented.')

    def is_useable(self):
        '''
        Returns if the tab is useable within the current environment
        '''
        return self._is_useable()

    def get_tab_panel(self):
        '''
        Returns the tab panel to show as a tab
        '''
        child, title = self._get_tab_panel()
        self._tab_panel = TabPanel(child=child, title=title)
        return self._tab_panel
