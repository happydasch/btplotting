from bokeh.layouts import column, row, gridplot, layout
from bokeh.models import Div, Spacer, Button
from ..helper.datatable import AnalysisTableGenerator
from ..tab import BacktraderPlottingTab


class AnalyzerTab(BacktraderPlottingTab):

    def __init__(self, app, figurepage, client=None):
        super(AnalyzerTab, self).__init__(app, figurepage, client)
        self.content = None

    def _is_useable(self):
        return len(self._figurepage.analyzers) > 0

    def _get_analyzer_info(self):
        tablegen = AnalysisTableGenerator(self._app.scheme, self._app.stylesheet)
        acolumns = []
        for analyzer in self._figurepage.analyzers:
            table_header, elements = tablegen.get_tables(analyzer)
            if table_header and elements:
                acolumns.append(column([table_header] + elements))
        info = gridplot(
            acolumns,
            ncols=self._app.scheme.analyzer_tab_num_cols,
            sizing_mode='stretch_width',
            toolbar_options={'logo': None})
        return info

    def _on_update_analyzer_info(self):
        self.content.children[1] = self._get_analyzer_info()

    def _create_content(self):
        title_area = []
        title = Div(
            text='Available Analyzer Results',
            css_classes=['tab-panel-title'],
            stylesheets=[self._app.stylesheet])
        title_area.append(row([title], width_policy='min'))
        if self._client:
            btn_refresh = Button(label='Refresh', width_policy='min')
            btn_refresh.on_click(self._on_update_analyzer_info)
            title_area.append(Spacer())
            title_area.append(row([btn_refresh], width_policy='min'))
        # set content in self
        return layout(
            [
                title_area,
                # initialize with info
                [self._get_analyzer_info()]
            ],
            sizing_mode='stretch_width')

    def _get_tab_panel(self):
        if self.content is None:
            self.content = self._create_content()
        return self.content, 'Analyzers'
