import collections
import itertools
import pkgutil

from enum import Enum

import backtrader as bt

from bokeh.models import Span
from bokeh.plotting import figure
from bokeh.models import HoverTool, CrosshairTool
from bokeh.models import LinearAxis, DataRange1d
from bokeh.models.formatters import NumeralTickFormatter
from bokeh.models import ColumnDataSource, FuncTickFormatter, \
    DatetimeTickFormatter, CustomJS

from .utils import get_datadomain, get_source_id
from .helper.label_resolver import datatarget2label, plotobj2label
from .helper.bokeh import convert_color, sanitize_source_name, \
    set_cds_columns_from_df
from .helper.marker import get_marker_info


class FigureType(Enum):
    (OBS, DATA, VOL, IND) = range(0, 4)

    @classmethod
    def get_obj(cls, name):
        if cls.DATA.name == name:
            return bt.AbstractDataBase
        elif cls.IND.name == name:
            return bt.IndicatorBase
        elif cls.OBS.name == name:
            return bt.ObserverBase
        else:
            raise Exception(f'Unknown name "{name}"')

    @classmethod
    def get_type(cls, obj):
        if isinstance(obj, bt.AbstractDataBase):
            return cls.DATA
        elif isinstance(obj, bt.IndicatorBase):
            return cls.IND
        elif isinstance(obj, bt.ObserverBase):
            return cls.OBS
        else:
            raise Exception(f'Unknown obj "{obj}"')


class HoverContainer(metaclass=bt.MetaParams):

    """
    Class to store information about hover tooltips. Will be filled
    while Bokeh glyphs are created. After all figures are complete,
    hovers will be applied by calling apply_hovertips
    """

    params = (('hover_tooltip_config', None),
              ('is_multidata', False))

    def __init__(self):
        self._hover_tooltips = []

        self._config = []
        input_config = (
            []
            if len(self.p.hover_tooltip_config) == 0
            else self.p.hover_tooltip_config.split(','))
        for c in input_config:
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
            apply: bool = src_obj is fig.master  # apply to own
            foreign = False
            if (not apply
                    and (isinstance(src_obj, bt.ObserverBase)
                         or isinstance(src_obj, bt.IndicatorBase))
                    and src_obj.plotinfo.subplot is False):
                # add objects that are on the same figure cause subplot
                # is False (for Indicators and Observers)
                # if plotmaster is set then it will decide where to add,
                # otherwise clock is used
                if src_obj.plotinfo.plotmaster is not None:
                    apply = src_obj.plotinfo.plotmaster is fig.master
                else:
                    apply = src_obj._clock is fig.master
            if not apply:
                for c in self._config:
                    if (isinstance(src_obj, c[0])
                            and isinstance(fig.master, c[1])):
                        apply = True
                        foreign = True
                        break

            if apply:
                prefix = ''
                top = True
                # prefix with data name if we got multiple datas
                if self.p.is_multidata and foreign:
                    if isinstance(src_obj, bt.IndicatorBase):
                        prefix = datatarget2label(src_obj.datas) + " - "
                    elif isinstance(src_obj, bt.AbstractDataBase):
                        prefix = datatarget2label([src_obj]) + " - "
                    top = False

                item = (prefix + label, tmpl)
                if top:
                    tooltips_top.append(item)
                else:
                    tooltips_bottom.append(item)

        # first apply all top hover then all bottoms
        for t in itertools.chain(tooltips_top, tooltips_bottom):
            hovertool.tooltips.append(t)

    def apply_hovertips(self, figures):

        """
        Add hovers to to all figures from the figures list
        """

        for f in figures:
            for t in f.figure.tools:
                if not isinstance(t, HoverTool):
                    continue

                self._apply_to_figure(f, t)
                break


class FigurePage(object):

    """
    FigurePage represents a strategy or optimization result
    """

    def __init__(self, obj):
        # columns the FigurePage is using
        # set to None for all, currently only datetime is used
        self.cds_cols = ['datetime']
        self.cds = ColumnDataSource()
        self.figures = []
        self.strategy = obj if isinstance(obj, bt.Strategy) else None
        self.analyzers = []
        # the whole generated model will we attached here after plotting
        self.model = None

    def get_datadomains(self):
        datadomain = set()
        for fe in self.figures:
            datadomain = datadomain.union(fe.get_datadomain())
        return list(datadomain)

    def set_data_from_df(self, df):
        set_cds_columns_from_df(df, self.cds, self.cds_cols)
        for f in self.figures:
            f.set_data_from_df(df)


class Figure(object):

    """
    Figure represents a figure plotted with bokeh

    It will wrap all data, indicators and observers being plotted on a
    single figure.
    The Figure is configured by calling plot()
    After the Figure is configured, it is required to fill the figure at
    least once with a DataFrame using set_data_from_df. After this, the
    ColumnDataSource is ready for use.
    """

    _tools = "pan,wheel_zoom,box_zoom,reset"

    _style_mpl2bokeh = {
        '-': 'solid',
        '--': 'dashed',
        ':': 'dotted',
        '.-': 'dotdash',
        '-.': 'dashdot',
    }

    _bar_width = 0.5

    def __init__(self, strategy, cds, hoverc, scheme, master,
                 plotorder, is_multidata, type):
        self._strategy = strategy
        self._scheme = scheme
        self._hover_line_set = False
        self._hover = None
        self._hoverc = hoverc
        self._coloridx = collections.defaultdict(lambda: -1)
        self._is_multidata = is_multidata
        self._page_cds = cds
        self.type = type
        self.cds_cols = []
        self.cds = ColumnDataSource()
        self.figure = None
        self.master = master
        self.plottab = None
        self.plotorder = plotorder
        # list of all datas that have been plotted to this figure
        self.datas = []
        self._init_figure()

    def _set_single_hover_renderer(self, renderer):

        """
        Sets this figure's hover to a single renderer
        """

        if self._hover_line_set:
            return

        self._hover.renderers = [renderer]
        self._hover_line_set = True

    def _add_hover_renderer(self, renderer):

        """
        Adds another hover render target. Only has effect if not single
        renderer has been set before
        """

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

        if self.type == FigureType.IND:
            aspectratio = self._scheme.ind_aspectratio
        elif self.type == FigureType.OBS:
            aspectratio = self._scheme.obs_aspectratio
        elif self.type == FigureType.VOL:
            aspectratio = self._scheme.vol_aspectratio
        elif self.type == FigureType.DATA:
            aspectratio = self._scheme.data_aspectratio
        else:
            raise Exception(f"Unknown type {self.type}")

        f = figure(
            tools=Figure._tools,
            x_axis_type='linear',
            aspect_ratio=aspectratio)
        # TODO: backend webgl (output_backend="webgl") removed due to this bug:
        # https://github.com/bokeh/bokeh/issues/7568
        f.y_range.range_padding = self._scheme.y_range_padding

        f.border_fill_color = convert_color(self._scheme.border_fill)

        f.xaxis.axis_line_color = convert_color(
            self._scheme.axis_line_color)
        f.yaxis.axis_line_color = convert_color(
            self._scheme.axis_line_color)
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

        f.xgrid.grid_line_color = convert_color(
            self._scheme.grid_line_color)
        f.ygrid.grid_line_color = convert_color(
            self._scheme.grid_line_color)
        f.title.text_color = convert_color(
            self._scheme.plot_title_text_color)

        f.left[0].formatter.use_scientific = False
        f.background_fill_color = convert_color(self._scheme.background_fill)

        # mechanism for proper date axis without gaps, thanks!
        # https://groups.google.com/a/continuum.io/forum/#!topic/bokeh/t3HkalO4TGA
        formatter_code = pkgutil.get_data(
            __name__,
            "templates/js/tick_formatter.js").decode()
        f.xaxis.formatter = FuncTickFormatter(
            args=dict(
                axis=f.xaxis[0],
                formatter=DatetimeTickFormatter(
                    microseconds=["%fus"],
                    milliseconds=["%3Nms", "%S.%3Ns"],
                    seconds=[self._scheme.axis_tickformat_seconds],
                    minsec=[self._scheme.axis_tickformat_minsec],
                    minutes=[self._scheme.axis_tickformat_minutes],
                    hourmin=[self._scheme.axis_tickformat_hourmin],
                    hours=[self._scheme.axis_tickformat_hours],
                    days=[self._scheme.axis_tickformat_days],
                    months=[self._scheme.axis_tickformat_months],
                    years=[self._scheme.axis_tickformat_years]),
                source=self._page_cds,
            ),
            code=formatter_code)

        ch = CrosshairTool(line_color=self._scheme.crosshair_line_color)
        f.tools.append(ch)

        hover_code = pkgutil.get_data(
            __name__,
            "templates/js/hover_tooltips.js").decode()
        h = HoverTool(
            tooltips=[(
                'Time',
                f'@datetime{{{self._scheme.hovertool_timeformat}}}')],
            mode="vline",
            formatters={'@datetime': 'datetime'},)
        callback = CustomJS(
            args=dict(source=self.cds, hover=h), code=hover_code)
        h.callback = callback
        f.tools.append(h)

        self._cross = ch
        self._hover = h
        self.figure = f

    def _set_yticks(self, obj):
        yticks = obj.plotinfo._get('plotyticks', [])
        if not yticks:
            yticks = obj.plotinfo._get('plotyhlines', [])

        if yticks:
            self.figure.yaxis.ticker = yticks

    def _plot_hlines(self, obj):
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
                        line_width=self._scheme.hlineswidth)
            self.figure.renderers.append(span)

    def _figure_append_title(self, title):
        # append to title
        if len(self.figure.title.text) > 0:
            self.figure.title.text += " | "
        self.figure.title.text += title

    def _plot_indicator_observer(self, obj, master):
        pl = plotobj2label(obj)

        self._figure_append_title(pl)
        indlabel = obj.plotlabel()
        plotinfo = obj.plotinfo

        is_multiline = obj.size() > 1
        for lineidx in range(obj.size()):
            line = obj.lines[lineidx]
            source_id = get_source_id(line)
            self.cds_cols.append(source_id)
            linealias = obj.lines._getlinealias(lineidx)

            lineplotinfo = getattr(obj.plotlines, '_%d' % lineidx, None)
            if not lineplotinfo:
                lineplotinfo = getattr(obj.plotlines, linealias, None)

            if not lineplotinfo:
                lineplotinfo = bt.AutoInfoClass()

            if lineplotinfo._get('_plotskip', False):
                continue

            marker = lineplotinfo._get("marker", None)
            method = lineplotinfo._get('_method', "line")

            color = getattr(lineplotinfo, "color", None)
            if color is None:
                if not lineplotinfo._get('_samecolor', False):
                    self._nextcolor()
                color = self._color()
            color = convert_color(color)

            kwglyphs = {'name': linealias}

            # either all individual lines of are displayed in the legend
            # or only the ind/obs as a whole
            label = indlabel
            if is_multiline and plotinfo.plotlinelabels:
                label += " " + (lineplotinfo._get("_name", "") or linealias)
            kwglyphs['legend_label'] = label

            if marker is not None:
                fnc_name, attrs, vals, updates = get_marker_info(marker)
                if not fnc_name or not hasattr(self.figure, fnc_name):
                    # provide alternative methods for not available methods
                    if fnc_name == "y":
                        fnc_name = "text"
                        attrs = ["text_color", "text_size"]
                        vals.update({"text": {"value": "y"}})
                    else:
                        raise Exception(
                            "Sorry, unsupported marker:"
                            + f" '{marker}'. Please report to GitHub.")
                        return
                # set kwglyph values
                kwglyphs['y'] = source_id
                for v in attrs:
                    val = None
                    if v in ['color', 'fill_color', 'text_color']:
                        val = {"value": color}
                    elif v in ['size']:
                        val = lineplotinfo.markersize
                    elif v in ['text_font_size']:
                        val = {"value": "%spx" % lineplotinfo.markersize}
                    elif v in ['text']:
                        val = {"value": marker[1:-1]}
                    if val is not None:
                        kwglyphs[v] = val
                for v in vals:
                    val = vals[v]
                    kwglyphs[v] = val
                for u in updates:
                    val = updates[u]
                    if u in kwglyphs:
                        kwglyphs[u] = max(
                            1, kwglyphs[u] + val)
                    else:
                        raise Exception(
                            f"{u} for {marker} is not set but needs to be set")
                glyph_fnc = getattr(self.figure, fnc_name)
            elif method == "bar":
                kwglyphs['bottom'] = 0
                kwglyphs['line_color'] = color
                kwglyphs['fill_color'] = color
                kwglyphs['width'] = self._bar_width
                kwglyphs['top'] = source_id

                glyph_fnc = self.figure.vbar
            elif method == "line":
                kwglyphs['line_width'] = 1
                kwglyphs['color'] = color
                kwglyphs['y'] = source_id

                linestyle = getattr(lineplotinfo, "ls", None)
                if linestyle is not None:
                    kwglyphs['line_dash'] = self._style_mpl2bokeh[linestyle]
                linewidth = getattr(lineplotinfo, "lw", None)
                if linewidth is not None:
                    kwglyphs['line_width'] = linewidth

                glyph_fnc = self.figure.line
            else:
                raise Exception(f"Unknown plotting method '{method}'")

            renderer = glyph_fnc("index", source=self.cds, **kwglyphs)

            # make sure the regular y-axis only scales to the normal
            # data (data + ind/obs) on 1st axis (not to e.g. volume
            # data on 2nd axis)
            self.figure.y_range.renderers.append(renderer)

            # for markers add additional renderer so hover pops up for all
            # of them
            if marker is None:
                self._set_single_hover_renderer(renderer)
            else:
                self._add_hover_renderer(renderer)

            # we need no suffix if there is just one line in the indicator
            hover_label_suffix = f" - {linealias}" if obj.size() > 1 else ""
            hover_label = indlabel + hover_label_suffix
            hover_data = f"@{source_id}{{{self._scheme.number_format}}}"
            self._hoverc.add_hovertip(hover_label, hover_data, obj)

        self._set_yticks(obj)
        self._plot_hlines(obj)

    def get_datadomain(self):
        """
        Returns the datadomain of the figure.
        """

        return get_datadomain(self.master)

    def set_data_from_df(self, df):
        if len(self.cds.column_names) < 1:
            set_cds_columns_from_df(df, self.cds, self.cds_cols)
        else:
            pass

    def plot(self, obj, master=None):
        if isinstance(obj, bt.AbstractDataBase):
            self.plot_data(obj)
        elif isinstance(obj, bt.IndicatorBase):
            self.plot_indicator(obj, master)
        elif isinstance(obj, bt.ObserverBase):
            self.plot_observer(obj, master)
        else:
            raise Exception(f"Unsupported plot object: {type(obj)}")

        # first object can apply config
        if len(self.datas) == 0:
            tab = getattr(obj.plotinfo, 'plottab', None)
            if tab is not None:
                self.plottab = tab
            order = getattr(obj.plotinfo, 'plotorder', None)
            if order is not None:
                self.plotorder = order

        self.datas.append(obj)

    def plot_data(self, data):
        source_id = get_source_id(data)
        self.cds_cols += [source_id + x for x in [
            'open', 'high', 'low', 'close',
            'colors_bars', 'colors_wicks',
            'colors_outline']]

        title = sanitize_source_name(datatarget2label([data]))
        self._figure_append_title(title)

        if self._scheme.style == 'line':
            if data.plotinfo.plotmaster is None:
                color = convert_color(self._scheme.loc)
            else:
                self._nextcolor(data.plotinfo.plotmaster)
                color = convert_color(self._color(data.plotinfo.plotmaster))

            renderer = self.figure.line(
                'index',
                source_id + 'close',
                source=self.cds,
                line_color=color,
                legend_label=title)
            self._set_single_hover_renderer(renderer)

            self._hoverc.add_hovertip("Close", f"@{source_id}close", data)
        elif self._scheme.style in ['bar', 'candle']:
            self.figure.segment(
                'index',
                source_id + 'high',
                'index',
                source_id + 'low',
                source=self.cds,
                color=source_id + 'colors_wicks',
                legend_label=title)
            renderer = self.figure.vbar(
                'index',
                self._bar_width,
                source_id + 'open',
                source_id + 'close',
                source=self.cds,
                fill_color=source_id + 'colors_bars',
                line_color=source_id + 'colors_outline',
                legend_label=title)

            self._set_single_hover_renderer(renderer)

            self._hoverc.add_hovertip(
                "Open",
                f"@{source_id}open{{{self._scheme.number_format}}}",
                data)
            self._hoverc.add_hovertip(
                "High",
                f"@{source_id}high{{{self._scheme.number_format}}}",
                data)
            self._hoverc.add_hovertip(
                "Low",
                f"@{source_id}low{{{self._scheme.number_format}}}",
                data)
            self._hoverc.add_hovertip(
                "Close",
                f"@{source_id}close{{{self._scheme.number_format}}}",
                data)
        else:
            raise Exception(f"Unsupported style '{self._scheme.style}'")

        # make sure the regular y-axis only scales to the normal data
        # on 1st axis (not to e.g. volume data on 2nd axis)
        self.figure.y_range.renderers = [renderer]

        if self._scheme.volume and self._scheme.voloverlay:
            self.plot_volume(data, self._scheme.voltrans, True)

    def plot_volume(self, data, alpha=1.0, extra_axis=False):

        """
        extra_axis displays a second axis (for overlay on data plotting)
        """

        source_id = get_source_id(data)
        self.cds_cols += [source_id + x for x in ['volume', 'colors_volume']]

        kwargs = {'fill_alpha': alpha,
                  'line_alpha': alpha,
                  'name': 'Volume',
                  'legend_label': 'Volume'}

        ax_formatter = NumeralTickFormatter(format=self._scheme.number_format)

        if extra_axis:
            source_data_axis = 'axvol'

            self.figure.extra_y_ranges = {source_data_axis: DataRange1d(
                range_padding=1.0 / self._scheme.volscaling,
                start=0,
            )}

            # use colorup
            ax_color = convert_color(self._scheme.volup)

            ax = LinearAxis(
                y_range_name=source_data_axis,
                formatter=ax_formatter,
                axis_label_text_color=ax_color,
                axis_line_color=ax_color,
                major_label_text_color=ax_color,
                major_tick_line_color=ax_color,
                minor_tick_line_color=ax_color)
            self.figure.add_layout(ax, 'left')
            kwargs['y_range_name'] = source_data_axis
        else:
            self.figure.yaxis.formatter = ax_formatter

        vbars = self.figure.vbar(
            'index',
            self._bar_width,
            f'{source_id}volume',
            0,
            source=self.cds,
            fill_color=f'{source_id}colors_volume',
            line_color=f'{source_id}colors_volume',
            **kwargs)

        # make sure the new axis only auto-scales to the volume data
        if extra_axis:
            self.figure.extra_y_ranges['axvol'].renderers = [vbars]

        self._hoverc.add_hovertip(
            "Volume",
            f"@{source_id}volume{{({self._scheme.number_format})}}",
            data)

    def plot_observer(self, obj, master):
        self._plot_indicator_observer(obj, master)

    def plot_indicator(self, obj, master):
        self._plot_indicator_observer(obj, master)
