#!/usr/bin/env python
# -*- coding: utf-8 -*-


from collections import defaultdict
from functools import partial

from pandas import DataFrame

from bokeh.models import ColumnDataSource
from bokeh.layouts import column
from bokeh.models.widgets import DataTable, TableColumn, \
    NumberFormatter, StringFormatter

from .webapp import Webapp


class OptBrowser:
    def __init__(self, app, optresults, usercolumns=None,
                 num_result_limit=None, sortcolumn=None,
                 sortasc=True, address='localhost', port=80,
                 autostart=False):
        self._usercolumns = {} if usercolumns is None else usercolumns
        self._num_result_limit = num_result_limit
        self._app = app
        self._sortcolumn = sortcolumn
        self._sortasc = sortasc
        self._optresults = optresults
        self._address = address
        self._port = port
        self._autostart = autostart

    def start(self, ioloop=None):
        webapp = Webapp(
            'Backtrader Optimization Result',
            'basic.html.j2',
            self._app.params.scheme,
            self.build_optresult_model,
            address=self._address,
            port=self._port,
            autostart=self._autostart)
        webapp.start(ioloop)

    def _build_optresult_selector(self, optresults):
        # 1. build a dict with all params and all user columns
        data_dict = defaultdict(list)
        for optres in optresults:
            for param_name, _ in optres[0].params._getitems():
                param_val = optres[0].params._get(param_name)
                data_dict[param_name].append(param_val)

            for usercol_label, usercol_fnc in self._usercolumns.items():
                data_dict[usercol_label].append(usercol_fnc(optres))

        # 2. build a pandas DataFrame
        df = DataFrame(data_dict)

        # 3. now sort and limit result
        if self._sortcolumn is not None:
            df = df.sort_values(by=[self._sortcolumn], ascending=self._sortasc)

        if self._num_result_limit is not None:
            df = df.head(self._num_result_limit)

        # 4. build column info for Bokeh table
        tab_columns = []

        for colname in data_dict.keys():
            formatter = NumberFormatter(format='0.000')

            if (len(data_dict[colname]) > 0
                    and isinstance(data_dict[colname][0], int)):
                formatter = StringFormatter()

            tab_columns.append(
                TableColumn(
                    field=colname,
                    title=f'{colname}',
                    sortable=False,
                    formatter=formatter))

        cds = ColumnDataSource(df)
        selector = DataTable(
            source=cds,
            columns=tab_columns,
            height=150,  # fixed height for selector
            width=0,  # set width to 0 so there is no min_width
            sizing_mode='stretch_width',
            fit_columns=True)
        return selector, cds

    def build_optresult_model(self, _=None):
        '''
        Generates and returns an interactive model for an OptResult
        or an OrderedOptResult
        '''

        def _get_model(selector_cds, idx: int):
            selector_cds.selected.indices = [idx]
            selected = selector_cds.data['index'][idx]
            return self._app.plot_optmodel(
                self._optresults[selected][0])

        # we have list of results, each result contains the result for
        # one strategy. we don't support having more than one strategy!
        if len(self._optresults) > 0 and len(self._optresults[0]) > 1:
            raise RuntimeError(
                'You passed on optimization result based on more than'
                + ' one strategy which is not supported!')

        selector, selector_cds = self._build_optresult_selector(
            self._optresults)

        # show the first result in list as default
        model = column(
            [selector, _get_model(selector_cds, 0)],
            sizing_mode='stretch_width')
        model.background = self._app.params.scheme.background_fill

        def update(selector_cds, name, old, new):
            if len(new) == 0:
                return
            stratidx = new[0]
            model.children[-1] = _get_model(
                selector_cds, stratidx)

        selector_cds.selected.on_change(
            'indices', partial(update, selector_cds))

        return model
