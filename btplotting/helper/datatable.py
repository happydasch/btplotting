from collections import OrderedDict
from enum import Enum

import backtrader as bt

from bokeh.models import ColumnDataSource, Div, TableColumn, DataTable, \
    DateFormatter, NumberFormatter, StringFormatter

from .params import get_params_str


# the height of a single row
ROW_HEIGHT = 25


class ColummDataType(Enum):
    DATETIME = 1
    FLOAT = 2
    INT = 3
    PERCENTAGE = 4
    STRING = 5


class TableGenerator:

    '''
    Table generator for key -> value tuples
    '''

    def __init__(self, stylesheet):
        self._stylesheet = stylesheet

    def get_table(self, data):
        table = [['Name'], ['Value']]
        cds = ColumnDataSource()
        columns = []
        for n, v in data.items():
            table[0].append(n)
            table[1].append(v)
        for i, c in enumerate(table):
            col_name = f'col{i}'
            cds.add(c[1:], col_name)
            columns.append(TableColumn(
                field=col_name,
                title=c[0]))
        column_height = len(table[0]) * ROW_HEIGHT
        dtable = DataTable(
            source=cds,
            columns=columns,
            index_position=None,
            height=column_height,
            width=0,  # set width to 0 so there is no min_width
            sizing_mode='stretch_width',
            fit_columns=True,
            stylesheets=[self._stylesheet])
        return dtable


class AnalysisTableGenerator:

    '''
    Table generator for analyzers
    '''

    def __init__(self, scheme, stylesheet):
        self._scheme = scheme
        self._stylesheet = stylesheet

    @staticmethod
    def _get_table_generic(analyzer):
        '''
        Returns two columns labeled '' and 'Value'
        '''
        table = [
            ['', ColummDataType.STRING],
            ['Value', ColummDataType.STRING]]

        def add_to_table(item, baselabel=''):
            if isinstance(item, dict):
                for ak, av in item.items():
                    label = f'{baselabel} - {ak}' if len(baselabel) > 0 else ak
                    if isinstance(av, (dict, bt.AutoOrderedDict, OrderedDict)):
                        add_to_table(av, label)
                    else:
                        table[0].append(label)
                        table[1].append(av)

        add_to_table(analyzer.get_analysis())
        return analyzer.__class__.__name__, [table]

    def _get_formatter(self, ctype):
        if ctype.name == ColummDataType.FLOAT.name:
            return NumberFormatter(format=self._scheme.number_format)
        elif ctype.name == ColummDataType.INT.name:
            return NumberFormatter()
        elif ctype.name == ColummDataType.DATETIME.name:
            return DateFormatter(format='%c')
        elif ctype.name == ColummDataType.STRING.name:
            return StringFormatter()
        elif ctype.name == ColummDataType.PERCENTAGE.name:
            return NumberFormatter(format='0.000 %')
        else:
            raise Exception(f'Unsupported ColumnDataType: "{ctype}"')

    def get_tables(self, analyzer):
        '''
        Return a header for this analyzer and one *or more* data tables.
        '''
        if hasattr(analyzer, 'get_analysis_table'):
            title, table_columns_list = analyzer.get_analysis_table()
        else:
            # Analyzer does not provide a table function. Use our generic one
            title, table_columns_list = __class__._get_table_generic(
                analyzer)

        # don't add empty analyzer
        if len(table_columns_list[0][0]) == 2:
            return None, None

        param_str = get_params_str(analyzer.params)
        if len(param_str) > 0:
            title += f' ({param_str})'

        elems = []
        for table_columns in table_columns_list:
            cds = ColumnDataSource()
            columns = []
            for i, c in enumerate(table_columns):
                col_name = f'col{i}'
                cds.add(c[2:], col_name)
                columns.append(TableColumn(
                    field=col_name,
                    title=c[0],
                    formatter=self._get_formatter(c[1])))
            # define height of column by multiplying count of rows
            # with ROW_HEIGHT
            column_height = len(table_columns[0]) * ROW_HEIGHT
            elems.append(DataTable(
                source=cds,
                columns=columns,
                index_position=None,
                height=column_height,
                width=0,  # set width to 0 so there is no min_width
                sizing_mode='stretch_width',
                fit_columns=True,
                stylesheets=[self._stylesheet]))

        table_title = Div(
            text=title,
            css_classes=['table-title'],
            stylesheets=[self._stylesheet])
        return table_title, elems
