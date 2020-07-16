from jinja2 import Environment, PackageLoader

from collections import defaultdict

import matplotlib.colors
import numpy as np
import pandas as pd

from bokeh.models import ColumnDataSource


def convert_color(color):
    '''
    if color is a float value then it is interpreted as a shade of grey
    and converted to the corresponding html color code
    '''

    try:
        val = round(float(color) * 255.0)
        hex_string = '#{0:02x}{0:02x}{0:02x}'.format(val)
        return hex_string
    except ValueError:
        return matplotlib.colors.to_hex(color)


def build_color_lines(df, scheme, col_open='open', col_close='close',
                      col_prefix=''):

    '''
    Creates columns with color infos for given DataFrame
    '''

    # build color strings from scheme
    colorup = convert_color(scheme.barup)
    colordown = convert_color(scheme.bardown)
    colorup_wick = convert_color(scheme.barup_wick)
    colordown_wick = convert_color(scheme.bardown_wick)
    colorup_outline = convert_color(scheme.barup_outline)
    colordown_outline = convert_color(scheme.bardown_outline)
    volup = convert_color(scheme.volup)
    voldown = convert_color(scheme.voldown)

    # build binary series determining if up or down bar
    is_up: pd.DataFrame = df[col_close] >= df[col_open]

    # we use the open-line as a indicator for NaN values
    nan_ref = df[col_open]

    color_df = pd.DataFrame(index=df.index)
    color_df[col_prefix + 'colors_bars'] = [
        np.nan if n != n
        else colorup if x
        else colordown
        for x, n in zip(is_up, nan_ref)]
    color_df[col_prefix + 'colors_wicks'] = [
        np.nan if n != n
        else colorup_wick if x
        else colordown_wick
        for x, n in zip(is_up, nan_ref)]
    color_df[col_prefix + 'colors_outline'] = [
        np.nan if n != n
        else colorup_outline if x
        else colordown_outline
        for x, n in zip(is_up, nan_ref)]
    color_df[col_prefix + 'colors_volume'] = [
        np.nan if n != n
        else volup if x
        else voldown
        for x, n in zip(is_up, nan_ref)]

    # convert to object since we want to hold str and NaN
    for c in color_df.columns:
        color_df[c] = color_df[c].astype(object)

    return color_df


def sanitize_source_name(name: str):
    '''
    removes illegal characters from source name to make it
    compatible with Bokeh
    '''

    forbidden_chars = ' (),.-/*:'
    for fc in forbidden_chars:
        name = name.replace(fc, '_')
    return name


def adapt_yranges(y_range, data, padding_factor=200.0):
    nnan_data = [x for x in data if not x != x]
    dmin = min(nnan_data, default=None)
    dmax = max(nnan_data, default=None)

    if dmin is None or dmax is None:
        return

    diff = ((dmax - dmin) or dmin) * padding_factor
    dmin -= diff
    dmax += diff

    if y_range.start is not None:
        dmin = min(dmin, y_range.start)
    y_range.start = dmin

    if y_range.end is not None:
        dmax = max(dmax, y_range.end)
    y_range.end = dmax


def generate_stylesheet(scheme, template="basic.css.j2"):
    env = Environment(loader=PackageLoader('btplotting', 'templates'))
    templ = env.get_template(template)

    css = templ.render(dict(
            datatable_row_color_even=scheme.table_color_even,
            datatable_row_color_odd=scheme.table_color_odd,
            datatable_header_color=scheme.table_header_color,
            tab_active_background_color=scheme.tab_active_background_color,
            tab_active_color=scheme.tab_active_color,

            tooltip_background_color=scheme.tooltip_background_color,
            tooltip_text_color_label=scheme.tooltip_text_label_color,
            tooltip_text_color_value=scheme.tooltip_text_value_color,
            body_background_color=scheme.body_background_color,
            tag_pre_background_color=scheme.tag_pre_background_color,
            tag_pre_text_color=scheme.tag_pre_text_color,
            headline_color=scheme.plot_title_text_color,
            text_color=scheme.text_color,
        )
    )
    return css


def set_cds_columns_from_df(df, cds, columns=None, dropna=True):
    '''
    Sets the ColumnDataSource columns based on the given DataFrame using
    the given columns. Only the given columns will be added, all will be
    added if columns=None
    '''

    if columns is None:
        columns = list(df.columns)
    c_df = df.loc[:, columns]
    # remove empty rows
    if dropna:
        c_df = c_df.dropna(how='all')
    # use text nan for nan values
    c_df.fillna('NaN')
    # add all columns and values
    for c in c_df:
        if c not in cds.column_names and c != 'datetime':
            cds.add(np.array(c_df.loc[:, c]), c)
        # ensure cds contains index
    if 'index' not in cds.column_names:
        cds.add(np.array(
            df.loc[c_df.index, 'index'], dtype=np.int64), 'index')
    # ensure cds contains corresponding datetime entries
    cds.add(np.array(
        df.loc[c_df.index, 'datetime'], dtype=np.datetime64), 'datetime')


def get_streamdata_from_df(df, columns=None):
    '''
    Creates stream data from df
    '''

    if columns is None:
        columns = list(df.columns)
    c_df = df.loc[:, columns]
    # use text NaN for nan values
    c_df.fillna('NaN')
    # ensure c_df contains index
    if 'index' not in c_df.columns:
        c_df.index = df.loc[c_df.index, 'index']
    # ensure c_df contains corresponding datetime entries
    if 'datetime' not in c_df.columns:
        c_df['datetime'] = df.loc[c_df.index, 'datetime']
    return ColumnDataSource.from_df(c_df)


def get_patchdata_from_series(series, cds, columns=None):

    p_data = defaultdict(list)
    s_data = defaultdict(list)
    idx_map = {d: idx for idx, d in enumerate(cds.data['index'])}
    # get the index in cds for series index
    if series['index'] in idx_map:
        idx = idx_map[series['index']]
    else:
        idx = False

    # create patch or stream data based on given series
    if idx is not False:
        for c in columns:
            if (series[c] == series[c]
                    and series[c] != cds.data[c][idx]):
                p_data[c].append((idx, series[c]))
        # ensure datetime is always patched
        if len(p_data) > 0 and 'datetime' not in p_data:
            p_data['datetime'].append((idx, series['datetime']))
    else:
        # add all columns to stream result. This may be needed if a value
        # was nan and therefore not added before
        for c in cds.column_names:
            val = series[c] if not pd.isna(series[c]) else 'NaN'
            s_data[c].append(val)
    return p_data, s_data


def sort_plotobjects(objs):
    objs.sort(key=lambda x: x.plotorder)


def get_plotmaster(obj):
    if obj is None:
        return None

    while True:
        pm = obj.plotinfo.plotmaster
        if pm is None:
            break
        else:
            obj = pm
    return obj
