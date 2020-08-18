import math

import backtrader as bt

from bokeh.layouts import column, row, gridplot, layout
from bokeh.models import Paragraph, Spacer, Button

from ..helper.params import get_params, paramval2str
from ..helper.label import obj2label, obj2data
from ..helper.datatable import TableGenerator
from ..tab import BacktraderPlottingTab


class MetadataTab(BacktraderPlottingTab):

    def __init__(self, app, figurepage, client=None):
        super(MetadataTab, self).__init__(app, figurepage, client)
        self.content = None

    def _is_useable(self):
        return True

    def _get_title(self, title):
        return Paragraph(
            text=title,
            css_classes=['table-title'])

    def _get_no_params(self):
        return Paragraph(text="No parameters", css_classes=['table-info'])

    def _get_parameter_table(self, params):
        tablegen = TableGenerator()
        params = get_params(params)
        if len(params) == 0:
            return self._get_no_params()
        else:
            for k, v in params.items():
                params[k] = paramval2str(k, v)
        return tablegen.get_table(params)

    def _get_values_table(self, values):
        tablegen = TableGenerator()
        if len(values) == 0:
            values[''] = ''
        return tablegen.get_table(values)

    def _get_strategy(self, strategy):
        columns = []
        childs = []
        childs.append(self._get_title(f'Strategy: {obj2label(strategy)}'))
        childs.append(self._get_parameter_table(strategy.params))
        for o in strategy.observers:
            childs.append(self._get_title(f'Observer: {obj2label(o)}'))
            childs.append(self._get_parameter_table(o.params))
        for a in strategy.analyzers:
            childs.append(self._get_title(f'Analyzer: {obj2label(a)}{" [Analysis Table]" if hasattr(a, "get_analysis_table") else ""}'))
            childs.append(self._get_parameter_table(a.params))
        columns.append(column(childs))
        return columns

    def _get_indicators(self, strategy):
        columns = []
        childs = []
        inds = strategy.getindicators()
        for i in inds:
            if isinstance(i, bt.IndicatorBase):
                childs.append(self._get_title(
                    f'Indicator: {obj2label(i)}@{obj2data(i)}'))
                childs.append(self._get_parameter_table(i.params))
        columns.append(column(childs))
        return columns

    def _get_datas(self, strategy):
        columns = []
        childs = []
        for data in strategy.datas:
            tabdata = {
                'DataName:': str(data._dataname).replace('|', '\\|'),
                'Timezone:': str(data._tz),
                'Live:': f'{"Yes" if data.islive() else "No"}',
                'Length:': len(data),
                'Granularity:': f'{data._compression} {bt.TimeFrame.getname(data._timeframe, data._compression)}',
            }
            # live trading does not have valid data parameters (other datas
            # might also not have)
            if not math.isinf(data.fromdate):
                tabdata['Time From:'] = str(bt.num2date(data.fromdate))
            if not math.isinf(data.todate):
                tabdata['Time To:'] = str(bt.num2date(data.todate))
            childs.append(self._get_title(f'Data Feed: {obj2label(data, True)}'))
            childs.append(self._get_values_table(tabdata))
        columns.append(column(childs))
        return columns

    def _get_metadata_columns(self, strategy):
        acolumns = []
        acolumns.extend(self._get_strategy(strategy))
        acolumns.extend(self._get_indicators(strategy))
        acolumns.extend(self._get_datas(strategy))
        return acolumns

    def _get_metadata_info(self):
        acolumns = self._get_metadata_columns(self._figurepage.strategy)
        info = gridplot(
            acolumns,
            ncols=self._app.scheme.metadata_tab_num_cols,
            sizing_mode='stretch_width',
            toolbar_options={'logo': None})
        return info

    def _on_update_metadata_info(self):
        self.content.children[1] = self._get_metadata_info()

    def _create_content(self):
        title_area = []
        title = Paragraph(
            text='Strategy Metadata Overview',
            css_classes=['panel-title'])
        title_area.append(row([title], width_policy='min'))
        if self._client:
            btn_refresh = Button(label='Refresh', width_policy='min')
            btn_refresh.on_click(self._on_update_metadata_info)
            title_area.append(Spacer())
            title_area.append(row([btn_refresh], width_policy='min'))
        # set content in self
        return layout(
            [
                title_area,
                # initialize with info
                [self._get_metadata_info()]
            ],
            sizing_mode='stretch_width')

    def _get_panel(self):
        if self.content is None:
            self.content = self._create_content()
        return self.content, 'Metadata'
