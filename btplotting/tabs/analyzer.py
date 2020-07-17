from bokeh.layouts import column, gridplot
from bokeh.models.widgets import Panel
from ..helper.datatable import AnalysisTableGenerator
from ..tab import BacktraderPlottingTab

# TODO add refresh button if client is set


class AnalyzerTab(BacktraderPlottingTab):

    def is_useable(self):
        return len(self.figurepage.analyzers) > 0

    def get_panel(self):
        tablegen = AnalysisTableGenerator(self.app.p.scheme)

        acolumns = []
        for analyzer in self.figurepage.analyzers:
            table_header, elements = tablegen.get_tables(analyzer)
            if table_header and elements:
                acolumns.append(column([table_header] + elements))

        childs = gridplot(
            acolumns,
            ncols=self.app.p.scheme.analyzer_tab_num_cols,
            sizing_mode='stretch_width',
            toolbar_options={'logo': None})

        return Panel(child=childs, title='Analyzers')
