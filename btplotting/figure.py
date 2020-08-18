import collections
import itertools
import pkgutil

from functools import partial
from enum import Enum

import backtrader as bt

from bokeh.models import Span
from bokeh.plotting import figure
from bokeh.models import HoverTool, CrosshairTool
from bokeh.models import LinearAxis, DataRange1d
from bokeh.models.formatters import NumeralTickFormatter
from bokeh.models import CustomJS, FuncTickFormatter, \
    DatetimeTickFormatter

from .cds import CDSObject
from .utils import get_source_id, get_clock_obj
from .helper.cds_ops import cds_op_gt, cds_op_lt, cds_op_non, \
    cds_op_color
from .helper.bokeh import convert_color, sanitize_source_name
from .helper.label import obj2label, obj2data
from .helper.marker import get_marker_info


class FigureType(Enum):
    (OBS, DATA, VOL, IND) = range(0, 4)

    @classmethod
    def get_obj(cls, name):
        if cls.DATA.name == name:
            return bt.AbstractDataBase
        elif cls.IND.name == name:
            return (bt.IndicatorBase, bt.MultiCoupler)
        elif cls.OBS.name == name:
            return bt.ObserverBase
        else:
            raise Exception(f'Unknown name "{name}"')

    @classmethod
    def get_type(cls, obj):
        if isinstance(obj, bt.AbstractDataBase):
            return cls.DATA
        elif isinstance(obj, (bt.IndicatorBase, bt.MultiCoupler)):
            return cls.IND
        elif isinstance(obj, bt.ObserverBase):
            return cls.OBS
        else:
            raise Exception(f'Unknown obj "{obj}"')


class HoverContainer(metaclass=bt.MetaParams):

    '''
    Class to store information about hover tooltips. Will be filled
    while Bokeh glyphs are created. After all figures are complete,
    hovers will be applied by calling apply_hovertips
    '''

    params = (('hover_tooltip_config', None),)

    def __init__(self):
        self._hover_tooltips = []

        self._config = []
        input_config = (
            []
            if len(self.p.hover_tooltip_config) == 0
            else self.p.hover_tooltip_config.split(','))
        for c in input_config:
            c = c.split('-')
            if len(c) != 2:
                raise RuntimeError(f'Invalid hover config entry "{c}"')
            self._config.append(
                (FigureType.get_obj(c[0]), FigureType.get_obj(c[1]))
            )

    def add_hovertip(self, label, tmpl, src_obj=None):
        self._hover_tooltips.append((label, tmpl, src_obj))

    def _apply_to_figure(self, fig, hovertool):
        # provide ordering by two groups
        tooltips_top = []
        tooltips_bottom = []
        for label, tmpl, src_obj in self._hover_tooltips:
            if src_obj is fig.master:
                item = (label, tmpl)
                tooltips_top.append(item)
            for i in fig.childs:
                if src_obj is i:
                    prefix = ''
                    if isinstance(src_obj, bt.AbstractDataBase):
                        prefix = obj2data(get_clock_obj(src_obj)) + " - "
                    item = (prefix + label, tmpl)
                    tooltips_bottom.append(item)
                    break

        # first apply all top hover then all bottoms
        for t in itertools.chain(tooltips_top, tooltips_bottom):
            hovertool.tooltips.append(t)

    def apply_hovertips(self, figures):
        '''
        Add hovers to to all figures from the figures list
        '''
        for f in figures:
            for t in f.figure.tools:
                if not isinstance(t, HoverTool):
                    continue
                self._apply_to_figure(f, t)
                break


class FigurePage(CDSObject):

    '''
    FigurePage represents a strategy or optimization result
    '''

    def __init__(self, obj, scheme):
        # columns the FigurePage is using
        # set to None for all, currently only datetime is used
        super(FigurePage, self).__init__(['datetime'])
        self.scheme = scheme
        self.figures = []
        self.analyzers = []
        self.strategy = obj if isinstance(obj, bt.Strategy) else None
        self.optreturn = obj if isinstance(obj, bt.OptReturn) else None
        # the whole generated model will we attached here after plotting
        self.model = None
        # add hover container if strategy
        self.hover = None
        self._set_hover_container()

    def _set_hover_container(self):
        '''
        Sets a new HoverContainer if a strategy is available
        '''
        if self.strategy is not None:
            self.hover = HoverContainer(
                hover_tooltip_config=self.scheme.hover_tooltip_config)
        else:
            self.hover = None

    def _set_linked_crosshairs(self, figures):
        '''
        Link crosshairs across all figures
        src:
        https://stackoverflow.com/questions/37965669/how-do-i-link-the-crosshairtool-in-bokeh-over-several-plots
        '''
        js_leave = ''
        js_move = 'if(cross.spans.height.location){\n'
        for i in range(len(figures) - 1):
            js_move += '\t\t\tother%d.spans.height.location = cb_obj.sx\n' % i
        js_move += '}else{\n'
        for i in range(len(figures) - 1):
            js_move += '\t\t\tother%d.spans.height.location = null\n' % i
            js_leave += '\t\t\tother%d.spans.height.location = null\n' % i
        js_move += '}'
        crosses = [CrosshairTool() for fig in figures]
        for i, fig in enumerate(figures):
            fig.figure.add_tools(crosses[i])
            args = {'fig': fig.figure, 'cross': crosses[i]}
            k = 0
            for j in range(len(figures)):
                if i != j:
                    args['other%d' % k] = crosses[j]
                    k += 1
            fig.figure.js_on_event(
                'mousemove', CustomJS(args=args, code=js_move))
            fig.figure.js_on_event(
                'mouseleave', CustomJS(args=args, code=js_leave))

    def set_cds_columns_from_df(self, df):
        '''
        Setup the FigurePage and Figures from DataFrame
        Note: this needs to be done at least once to prepare
        all cds with columns
        '''
        super(FigurePage, self).set_cds_columns_from_df(df)
        for f in self.figures:
            f.set_cds_columns_from_df(df)

    def apply(self):
        '''
        Apply additional configuration after all figures are set
        Note: this method will be called from BacktraderPlotting
        '''
        if self.hover:
            self.hover.apply_hovertips(self.figures)
        self._set_linked_crosshairs(self.figures)

    def reset(self):
        '''
        Resets the FigurePage
        '''
        self.cds_reset()
        self.figures = []
        self.analyzers = []
        self._set_hover_container()


class Figure(CDSObject):

    '''
    Figure represents a figure plotted with bokeh

    It will wrap all data, indicators and observers being plotted on a
    single figure.
    The Figure is configured by calling plot()
    After the Figure is configured, it is required to fill the figure at
    least once with a DataFrame using set_cds_columns_from_df. After this,
    the CDSObject is ready for use.

    backtrader plotting options:
    https://www.backtrader.com/docu/plotting/plotting/
    '''

    _tools = 'pan,wheel_zoom,box_zoom,reset'

    _style_mpl2bokeh = {
        '-': 'solid',
        '--': 'dashed',
        ':': 'dotted',
        '.-': 'dotdash',
        '-.': 'dashdot',
    }

    _bar_width = 0.5

    def __init__(self, fp, scheme, master, childs, type=None):
        super(Figure, self).__init__([])
        self._fp = fp
        self._scheme = scheme
        self._hover_line_set = False
        self._hover = None
        self._coloridx = collections.defaultdict(lambda: -1)
        self._type = type
        self._data_cols = []
        self.master = master
        self.childs = childs
        self.figure = None
        # initialize figure with scheme settings
        self._init_figure()

    def _set_single_hover_renderer(self, renderer):
        '''
        Sets this figure's hover to a single renderer
        '''
        if self._hover_line_set:
            return
        self._hover.renderers = [renderer]
        self._hover_line_set = True

    def _add_hover_renderer(self, renderer):
        '''
        Adds another hover render target. Only has effect if not single
        renderer has been set before
        '''
        if self._hover_line_set:
            return
        if isinstance(self._hover.renderers, list):
            self._hover.renderers.append(renderer)
        else:
            self._hover.renderers = [renderer]

    def _nextcolor(self, key=None):
        self._coloridx[key] += 1
        return self._coloridx[key]

    def _color(self, key=None):
        return convert_color(self._scheme.color(self._coloridx[key]))

    def _init_figure(self):
        '''
        Initializes the figure
        '''
        ftype = self.get_type()
        if ftype == FigureType.IND:
            aspectratio = self._scheme.ind_aspectratio
        elif ftype == FigureType.OBS:
            aspectratio = self._scheme.obs_aspectratio
        elif ftype == FigureType.VOL:
            aspectratio = self._scheme.vol_aspectratio
        elif ftype == FigureType.DATA:
            aspectratio = self._scheme.data_aspectratio
        else:
            raise Exception(f'Unknown type "{ftype}"')

        f = figure(
            width=1000,
            tools=Figure._tools,
            x_axis_type='linear',
            # backend webgl removed due to this bug:
            # https://github.com/bokeh/bokeh/issues/7568
            # also line styles do not work with webgl
            # output_backend='webgl',
            aspect_ratio=aspectratio)

        f.y_range.range_padding = self._scheme.y_range_padding
        # remove any spacing if there is no title, so there is no spacing
        # between plots
        if not self._scheme.plot_title:
            f.min_border_bottom = 0
            f.min_border_top = 0

        f.border_fill_color = convert_color(self._scheme.border_fill)

        f.xaxis.axis_line_color = convert_color(self._scheme.axis_line_color)
        f.yaxis.axis_line_color = convert_color(self._scheme.axis_line_color)
        f.xaxis.minor_tick_line_color = convert_color(
            self._scheme.tick_line_color)
        f.yaxis.minor_tick_line_color = convert_color(
            self._scheme.tick_line_color)
        f.xaxis.major_tick_line_color = convert_color(
            self._scheme.tick_line_color)
        f.yaxis.major_tick_line_color = convert_color(
            self._scheme.tick_line_color)

        f.xaxis.major_label_text_color = convert_color(
            self._scheme.axis_label_text_color)
        f.yaxis.major_label_text_color = convert_color(
            self._scheme.axis_label_text_color)

        f.xgrid.grid_line_color = convert_color(self._scheme.grid_line_color)
        f.ygrid.grid_line_color = convert_color(self._scheme.grid_line_color)
        f.title.text_color = convert_color(self._scheme.plot_title_text_color)

        f.left[0].formatter.use_scientific = False
        f.background_fill_color = convert_color(self._scheme.background_fill)

        # mechanism for proper date axis without gaps, thanks!
        # https://groups.google.com/a/continuum.io/forum/#!topic/bokeh/t3HkalO4TGA
        formatter_code = pkgutil.get_data(
            __name__,
            'templates/js/tick_formatter.js').decode()
        f.xaxis.formatter = FuncTickFormatter(
            args=dict(
                axis=f.xaxis[0],
                formatter=DatetimeTickFormatter(
                    microseconds=['%fus'],
                    milliseconds=['%3Nms', '%S.%3Ns'],
                    seconds=[self._scheme.axis_tickformat_seconds],
                    minsec=[self._scheme.axis_tickformat_minsec],
                    minutes=[self._scheme.axis_tickformat_minutes],
                    hourmin=[self._scheme.axis_tickformat_hourmin],
                    hours=[self._scheme.axis_tickformat_hours],
                    days=[self._scheme.axis_tickformat_days],
                    months=[self._scheme.axis_tickformat_months],
                    years=[self._scheme.axis_tickformat_years]),
                source=self._fp.cds,
            ),
            code=formatter_code)

        hover_code = pkgutil.get_data(
            __name__,
            'templates/js/hover_tooltips.js').decode()
        h = HoverTool(
            tooltips=[
                ('Time',
                 f'@datetime{{{self._scheme.hovertool_timeformat}}}')],
            mode='vline',
            formatters={'@datetime': 'datetime'},)
        callback = CustomJS(
            args=dict(source=self.cds, hover=h), code=hover_code)
        h.callback = callback
        f.tools.append(h)
        self._hover = h

        # set figure
        self.figure = f

    def _figure_append_title(self, title):
        '''
        Appends a title to figure
        '''
        if len(self.figure.title.text) > 0:
            self.figure.title.text += ' | '
        self.figure.title.text += title

    def _figure_append_renderer(self, func, marker=False, **kwargs):
        '''
        Appends renderer to figure and updates the hover renderer
        '''
        if 'source' not in kwargs:
            kwargs['source'] = self.cds
        elif kwargs['source'] is None:
            del kwargs['source']
        renderer = func(**kwargs)

        # add renderer to y_range
        if 'y_range_name' in kwargs:
            range = self.figure.extra_y_ranges[kwargs['y_range_name']]
            if isinstance(range.renderers, list):
                range.renderers = [renderer]
            else:
                range.renderers.append(renderer)
        else:
            # if no y_range id provided, use default y_range
            if not isinstance(self.figure.y_range.renderers, list):
                self.figure.y_range.renderers = [renderer]
            else:
                self.figure.y_range.renderers.append(renderer)

        # for markers add additional renderer so hover pops up for all
        # of them (this will only apply if no line renderer is set)
        if marker:
            self._add_hover_renderer(renderer)
        else:
            self._set_single_hover_renderer(renderer)

    def _plot_indicator_observer(self, obj):
        '''
        Common method to plot observer and indicator lines
        '''
        if self._scheme.plot_title:
            self._figure_append_title(obj2label(obj, True))
        plotinfo = obj.plotinfo

        for lineidx, line in enumerate(obj.lines):
            source_id = get_source_id(line)
            self.set_cds_col(source_id)
            linealias = obj.lines._getlinealias(lineidx)

            # get plotinfo
            lineplotinfo = getattr(obj.plotlines, '_%d' % lineidx, None)
            if not lineplotinfo:
                lineplotinfo = getattr(obj.plotlines, linealias, None)
            if not lineplotinfo or lineplotinfo._get('_plotskip', False):
                continue

            # check if marker and get method to plot line
            marker = lineplotinfo._get('marker', None)
            method = lineplotinfo._get('_method', None)
            if not marker and not method:
                method = 'line'
            elif not method:
                if (getattr(lineplotinfo, 'ls', None)
                        or getattr(lineplotinfo, 'lw', None)
                        or getattr(lineplotinfo, 'drawstyle', None)):
                    method = 'line'

            # get a color
            color = getattr(lineplotinfo, 'color', None)
            if color is None:
                if not lineplotinfo._get('_samecolor', False):
                    self._nextcolor()
                color = self._color()
            color = convert_color(color)

            # either all individual lines of are displayed in the legend
            # or only the ind/obs as a whole
            label = obj2label(obj, True)

            if obj.size() > 1 and plotinfo.plotlinelabels:
                label += ' ' + (lineplotinfo._get('_name', None)
                                or linealias)

            if marker is not None:
                kwglyph = {'x': 'index', 'name': linealias + 'marker',
                           'legend_label': label}
                fnc_name, attrs, vals, updates = get_marker_info(marker)
                markersize = (7
                              if not hasattr(lineplotinfo, 'markersize')
                              else lineplotinfo.markersize)

                if not fnc_name or not hasattr(self.figure, fnc_name):
                    # provide alternative methods for not available methods
                    if fnc_name == 'y':
                        fnc_name = 'text'
                        attrs = ['text_color', 'text_size']
                        vals.update({'text': {'value': 'y'}})
                    else:
                        raise Exception(
                            'Sorry, unsupported marker:'
                            + f' "{marker}". Please report to GitHub.')
                        return
                # set kwglyph values
                kwglyph['y'] = source_id
                for v in attrs:
                    val = None
                    if v in ['color', 'fill_color', 'text_color']:
                        val = {'value': color}
                    elif v in ['size']:
                        val = markersize
                    elif v in ['text_font_size']:
                        val = {'value': '%spx' % markersize}
                    elif v in ['text']:
                        val = {'value': marker[1:-1]}
                    if val is not None:
                        kwglyph[v] = val
                for v in vals:
                    val = vals[v]
                    kwglyph[v] = val
                for u in updates:
                    val = updates[u]
                    if u in kwglyph:
                        kwglyph[u] = max(
                            1, kwglyph[u] + val)
                    else:
                        raise Exception(
                            f'{u} for {marker} is not set but needs to be set')
                glyph_fnc = getattr(self.figure, fnc_name)
                # append renderer
                self._figure_append_renderer(
                    glyph_fnc, marker=marker, **kwglyph)

            if method == 'bar':
                kwglyph = {'x': 'index', 'name': linealias + 'bar',
                           'legend_label': label}
                kwglyph['level'] = 'underlay'
                kwglyph['top'] = source_id
                kwglyph['bottom'] = 0
                kwglyph['line_color'] = color
                kwglyph['fill_color'] = color
                kwglyph['width'] = self._bar_width
                glyph_fnc = self.figure.vbar
                # append renderer
                self._figure_append_renderer(
                    glyph_fnc, marker=None, **kwglyph)
            elif method == 'line':
                kwglyph = {'x': 'index', 'name': linealias + 'line',
                           'legend_label': label}
                kwglyph['level'] = 'underlay'
                kwglyph['line_width'] = 1
                kwglyph['color'] = color
                kwglyph['y'] = source_id
                linestyle = getattr(lineplotinfo, 'ls', None)
                if linestyle:
                    kwglyph['line_dash'] = self._style_mpl2bokeh[linestyle]
                linewidth = getattr(lineplotinfo, 'lw', None)
                if linewidth:
                    kwglyph['line_width'] = linewidth
                drawstyle = getattr(lineplotinfo, 'drawstyle', None)
                if drawstyle:
                    if drawstyle == 'steps-mid':
                        kwglyph['mode'] = 'center'
                    elif drawstyle == 'steps-right':
                        kwglyph['mode'] = 'after'
                    else:
                        kwglyph['mode'] = 'before'
                    glyph_fnc = self.figure.step
                else:
                    glyph_fnc = self.figure.line
                # append renderer
                self._figure_append_renderer(
                    glyph_fnc, marker=None, **kwglyph)

            # chek for fill_between
            for ftype, fop in [
                    ('_gt', cds_op_gt),
                    ('_lt', cds_op_lt),
                    ('', cds_op_non)]:
                fattr = '_fill' + ftype
                fref, fcolor = lineplotinfo._get(fattr, (None, None))
                if fref is not None:
                    # set name for new column
                    col_name = source_id + ftype
                    # check if ref is a number or a column
                    if isinstance(fref, str):
                        source_id_other = get_source_id(
                            getattr(obj, fref))
                    else:
                        source_id_other = fref
                    # create new cds column
                    col = (col_name, source_id, source_id_other, fop)
                    self.set_cds_col(col)
                    # set alpha and check color
                    falpha = self._scheme.fillalpha
                    if isinstance(fcolor, tuple):
                        fcolor, falpha = fcolor
                    fcolor = convert_color(fcolor)
                    # create varea
                    kwargs = {
                        'x': 'index',
                        'y1': source_id,
                        'y2': col_name,
                        'fill_alpha': falpha,
                        'color': fcolor,
                        'legend_label': label,
                        'level': 'underlay'}
                    self._figure_append_renderer(
                        self.figure.varea, **kwargs)

            # set hover label
            hover_label = f'{obj2label(obj)} - {linealias}'
            hover_data = f'@{source_id}{{{self._scheme.number_format}}}'
            if hover_label:
                self._fp.hover.add_hovertip(hover_label, hover_data, obj)

        self._set_yticks(obj)
        self._plot_hlines(obj)

    def _set_yticks(self, obj):
        '''
        Plots ticks on y axis
        '''
        yticks = obj.plotinfo._get('plotyticks', [])
        if not yticks:
            yticks = obj.plotinfo._get('plotyhlines', [])
        if yticks:
            self.figure.yaxis.ticker = yticks

    def _plot_hlines(self, obj):
        '''
        Plots horizontal lines on figure
        '''
        hlines = obj.plotinfo._get('plothlines', [])
        if not hlines:
            hlines = obj.plotinfo._get('plotyhlines', [])
        # Horizontal Lines
        hline_color = convert_color(self._scheme.hlinescolor)
        for hline in hlines:
            span = Span(location=hline,
                        dimension='width',
                        line_color=hline_color,
                        line_dash=self._style_mpl2bokeh[
                            self._scheme.hlinesstyle],
                        line_width=self._scheme.hlineswidth,
                        level='underlay')
            self.figure.renderers.append(span)

    def fill_nan(self):
        '''
        Workaround for bokeh issue with nan

        In most cases nan should not be filled, only if style is not line
        for data. Since with nan values in data there will be gaps, this
        will happen when patching data.

        See: DataHandler for usage of fill_nan()
        '''
        if self.get_type() == FigureType.DATA and self._scheme.style != 'line':
            return self._data_cols
        return []

    def get_type(self):
        '''
        Returns the FigureType of this Figure
        '''
        if self._type is None:
            return FigureType.get_type(self.master)
        return self._type

    def get_plotorder(self):
        '''
        Returns the plotorder of this Figure
        '''
        return self.master.plotinfo.plotorder

    def get_plotid(self):
        '''
        Returns the plotid of the figure
        '''
        return self.master.plotinfo.plotid

    def get_plottab(self):
        '''
        Returns the plottab of this Figure
        '''
        return getattr(self.master.plotinfo, 'plottab', None)

    def plot(self, obj):
        '''
        Common plot method
        '''
        if FigureType.get_type(obj) == FigureType.DATA:
            self.plot_data(obj)
        elif FigureType.get_type(obj) == FigureType.IND:
            self.plot_indicator(obj)
        elif FigureType.get_type(obj) == FigureType.OBS:
            self.plot_observer(obj)
        else:
            raise Exception(f'Unsupported plot object: "{type(obj)}"')

    def plot_data(self, data):
        '''
        Plot method for data
        '''
        source_id = get_source_id(data)
        self._data_cols = [
            source_id + x for x in ['open', 'high', 'low', 'close']]
        self.set_cds_col(self._data_cols)
        # create color columns
        colorup = convert_color(self._scheme.barup)
        colordown = convert_color(self._scheme.bardown)
        self.set_cds_col((
            source_id + 'colors_bars',
            source_id + 'open',
            source_id + 'close',
            partial(cds_op_color,
                    color_up=colorup,
                    color_down=colordown)))
        colorup_wick = convert_color(self._scheme.barup_wick)
        colordown_wick = convert_color(self._scheme.bardown_wick)
        self.set_cds_col((
            source_id + 'colors_wicks',
            source_id + 'open',
            source_id + 'close',
            partial(cds_op_color,
                    color_up=colorup_wick,
                    color_down=colordown_wick)))
        colorup_outline = convert_color(self._scheme.barup_outline)
        colordown_outline = convert_color(self._scheme.bardown_outline)
        self.set_cds_col((
            source_id + 'colors_outline',
            source_id + 'open',
            source_id + 'close',
            partial(cds_op_color,
                    color_up=colorup_outline,
                    color_down=colordown_outline)))

        title = sanitize_source_name(obj2label(data))
        if self._scheme.plot_title:
            self._figure_append_title(title)

        if self._scheme.style == 'line':
            if data.plotinfo.plotmaster is None:
                color = convert_color(self._scheme.loc)
            else:
                self._nextcolor(data.plotinfo.plotmaster)
                color = convert_color(self._color(data.plotinfo.plotmaster))
            kwargs = {
                'x': 'index',
                'y': source_id + 'close',
                'line_color': color,
                'legend_label': title
            }
            # append renderer
            self._figure_append_renderer(self.figure.line, **kwargs)
            # set hover label
            self._fp.hover.add_hovertip('Close', f'@{source_id}close', data)
        elif self._scheme.style in ['bar', 'candle']:
            kwargs_seg = {
                'x0': 'index',
                'y0': source_id + 'high',
                'x1': 'index',
                'y1': source_id + 'low',
                'color': source_id + 'colors_wicks',
                'legend_label': title
            }
            kwargs_vbar = {
                'x': 'index',
                'width': self._bar_width,
                'top': source_id + 'open',
                'bottom': source_id + 'close',
                'fill_color': source_id + 'colors_bars',
                'line_color': source_id + 'colors_outline',
                'legend_label': title
            }
            # append renderer
            self._figure_append_renderer(self.figure.segment, **kwargs_seg)
            self._figure_append_renderer(self.figure.vbar, **kwargs_vbar)
            # set hover label
            self._fp.hover.add_hovertip(
                'Open',
                f'@{source_id}open{{{self._scheme.number_format}}}',
                data)
            self._fp.hover.add_hovertip(
                'High',
                f'@{source_id}high{{{self._scheme.number_format}}}',
                data)
            self._fp.hover.add_hovertip(
                'Low',
                f'@{source_id}low{{{self._scheme.number_format}}}',
                data)
            self._fp.hover.add_hovertip(
                'Close',
                f'@{source_id}close{{{self._scheme.number_format}}}',
                data)
        else:
            raise Exception(f'Unsupported style "{self._scheme.style}"')

        if self._scheme.volume and self._scheme.voloverlay:
            self.plot_volume(data, self._scheme.voltrans, True)

    def plot_volume(self, data, alpha=1.0, extra_axis=False):
        '''
        Plot method for volume
        extra_axis: displays a second axis (for overlay on data plotting)
        '''
        source_id = get_source_id(data)
        self.set_cds_col(source_id + 'volume')
        # create color columns
        volup = convert_color(self._scheme.volup)
        voldown = convert_color(self._scheme.voldown)
        self.set_cds_col((
            source_id + 'colors_volume',
            source_id + 'open',
            source_id + 'close',
            partial(cds_op_color,
                    color_up=volup,
                    color_down=voldown)))

        # prepare bar kwargs
        kwargs = {
            'x': 'index',
            'width': self._bar_width,
            'top': source_id + 'volume',
            'bottom': 0,
            'fill_color': source_id + 'colors_volume',
            'line_color': source_id + 'colors_volume',
            'fill_alpha': alpha,
            'line_alpha': alpha,
            'name': 'Volume',
            'legend_label': 'Volume'}

        # set axis
        ax_formatter = NumeralTickFormatter(format=self._scheme.number_format)
        if extra_axis:
            source_data_axis = 'axvol'
            # use colorup
            ax_color = convert_color(self._scheme.volup)
            # use only one additional axis to prevent multiple axis being added
            # to a single figure
            ax = self.figure.select_one({'name': source_data_axis})
            if ax is None:
                # create new axis if not already available
                self.figure.extra_y_ranges = {source_data_axis: DataRange1d(
                    range_padding=1.0 / self._scheme.volscaling,
                    start=0)}
                ax = LinearAxis(
                    name=source_data_axis,
                    y_range_name=source_data_axis,
                    formatter=ax_formatter,
                    axis_label_text_color=ax_color,
                    axis_line_color=ax_color,
                    major_label_text_color=ax_color,
                    major_tick_line_color=ax_color,
                    minor_tick_line_color=ax_color)
                self.figure.add_layout(ax, self._scheme.vol_axis_location)
            kwargs['y_range_name'] = source_data_axis
        else:
            self.figure.yaxis.formatter = ax_formatter

        # append renderer
        self._figure_append_renderer(self.figure.vbar, **kwargs)
        # set hover label
        self._fp.hover.add_hovertip(
            'Volume',
            f'@{source_id}volume{{({self._scheme.number_format})}}',
            data)

    def plot_observer(self, obj):
        '''
        Plot method for observer
        '''
        self._plot_indicator_observer(obj)

    def plot_indicator(self, obj):
        '''
        Plot method for indicator
        '''
        self._plot_indicator_observer(obj)

    def apply(self):
        '''
        Apply additional configuration after the figure was plotted
        Note: this method will be called from BacktraderPlotting
        '''
        # apply legend configuration to figure
        legend = self.figure.legend
        legend.background_fill_alpha = self._scheme.legendtrans
        legend.click_policy = self._scheme.legend_click
        legend.location = self._scheme.legend_location
        legend.background_fill_color = self._scheme.legend_background_color
        legend.label_text_color = self._scheme.legend_text_color
        legend.orientation = self._scheme.legend_orientation
