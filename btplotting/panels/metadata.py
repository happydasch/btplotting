import math

import backtrader as bt

from bokeh.layouts import column, gridplot
from bokeh.models import Panel, Paragraph

from ..utils import get_params, paramval2str
from ..helper.label_resolver import indicator2fullid
from ..helper.datatable import TableGenerator


def _get_title(title):
    return Paragraph(
        text=title,
        css_classes=['table_title'])


def _get_no_params():
    return Paragraph(text="No parameters", css_classes=['table_info'])


def _get_parameter_table(params):
    tablegen = TableGenerator()
    params = get_params(params)
    if len(params) == 0:
        return _get_no_params()
    else:
        for k, v in params.items():
            params[k] = paramval2str(k, v)
    return tablegen.get_table(params)


def _get_values_table(values):
    tablegen = TableGenerator()
    if len(values) == 0:
        values[''] = ''
    return tablegen.get_table(values)


def _get_strategy(strategy):
    columns = []
    childs = []
    childs.append(_get_title(f'Strategy: {strategy.__class__.__name__}'))
    childs.append(_get_parameter_table(strategy.params))
    for o in strategy.observers:
        childs.append(_get_title(f'Observer: {o.__class__.__name__}'))
        childs.append(_get_parameter_table(o.params))
    for a in strategy.analyzers:
        childs.append(_get_title(f'Analyzer: {a.__class__.__name__}'))
        childs.append(_get_parameter_table(a.params))
    columns.append(column(childs))
    return columns


def _get_indicators(strategy):
    columns = []
    childs = []
    for i in strategy.getindicators():
        childs.append(_get_title(
            f'Indicator: {i.__class__.__name__} @ {indicator2fullid(i)}'))
        childs.append(_get_parameter_table(i.params))
    columns.append(column(childs))
    return columns


def _get_datas(strategy):
    columns = []
    childs = []
    for data in strategy.datas:
        tabdata = {
            'DataName:': str(data._dataname).replace("|", "\\|"),
            'Timezone:': str(data._tz),
            'Number of bars:': len(data),
            'Bar Length:': f"{data._compression} {bt.TimeFrame.getname(data._timeframe, data._compression)}",
        }
        # live trading does not have valid data parameters (other datas
        # might also not have)
        if not math.isinf(data.fromdate):
            tabdata['Time From:'] = bt.num2date(data.fromdate)
        if not math.isinf(data.todate):
            tabdata['Time To:'] = bt.num2date(data.todate)
        childs.append(_get_title(f'Data Feed: {data.__class__.__name__}'))
        childs.append(_get_values_table(tabdata))
    columns.append(column(childs))
    return columns


def _get_metadata_columns(strategy):
    acolumns = []
    acolumns.extend(_get_strategy(strategy))
    acolumns.extend(_get_indicators(strategy))
    acolumns.extend(_get_datas(strategy))
    return acolumns


def get_metadata_panel(app, figurepage, client):
    acolumns = _get_metadata_columns(figurepage.strategy)
    childs = gridplot(
        acolumns,
        ncols=app.p.scheme.metadata_tab_num_cols,
        sizing_mode='stretch_width',
        toolbar_options={'logo': None})
    return Panel(child=childs, title="Metadata")
