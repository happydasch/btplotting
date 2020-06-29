from bokeh.layouts import column, gridplot
from bokeh.models.widgets import Panel
from ..helper.datatable import AnalysisTableGenerator


def get_analyzer_panel(app, figurepage, client):
    tablegen = AnalysisTableGenerator(app.p.scheme)

    if len(figurepage.analyzers) == 0:
        return None

    acolumns = []
    for analyzer in figurepage.analyzers:
        table_header, elements = tablegen.get_tables(analyzer)
        if table_header and elements:
            acolumns.append(column([table_header] + elements))

    childs = gridplot(
        acolumns,
        ncols=app.p.scheme.analyzer_tab_num_cols,
        sizing_mode='stretch_width',
        toolbar_options={'logo': None})

    return Panel(child=childs, title='Analyzers')
