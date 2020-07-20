from collections import defaultdict
import datetime
import itertools
import logging
import re
import os
import sys
import tempfile

import backtrader as bt

import pandas as pd

from bokeh.models.widgets import Panel, Tabs
from bokeh.layouts import gridplot

from bokeh.embed import file_html
from bokeh.resources import CDN
from bokeh.util.browser import view

from jinja2 import Environment, PackageLoader

from .schemes import Scheme, Blackly

from .utils_new import get_dataname
from .utils import get_indicator_data, get_datadomain, \
    filter_by_datadomain, get_source_id
from .figure import FigurePage, FigureType, Figure, HoverContainer
from .clock import ClockGenerator, ClockHandler
from .helper.label import obj2label
from .helper.bokeh import generate_stylesheet, build_color_lines, \
    get_plotmaster
from .tab import BacktraderPlottingTab
from .tabs import AnalyzerTab, MetadataTab, LogTab

_logger = logging.getLogger(__name__)


if 'ipykernel' in sys.modules:
    from IPython.core.display import display, HTML  # noqa
    from bokeh.io import output_notebook, show
    output_notebook()


class BacktraderPlotting(metaclass=bt.MetaParams):

    '''
    BacktraderPlotting is the main component

    It acts as a connection between backtrader and the plotting functionality.
    It acts of multiple strategies and creates a figurepage containing all
    figures to plot.

    The methods plot and show will be called from within backtrader.
    plot -> the given strategy will be mapped to a empty figurepage
    show -> all figurepages will be filled with data and plotted

    The live client also uses this class to generate all figures to plot.

    TODO
    -datadomain should be cleaned up (provide one or more datadomains)
    '''

    params = (
        # scheme object for styling plots
        ('scheme', Blackly()),
        # output filename when running backtest
        ('filename', None),
        # individual plot options
        ('plotconfig', None),
        # output mode for plotting: show, save, memory
        ('output_mode', 'show'),
        # custom tabs
        ('tabs', []),
        # should default tabs be used
        ('use_default_tabs', True),
    )

    def __init__(self, **kwargs):
        # apply additional parameters to override / set scheme settings
        for pname, pvalue in kwargs.items():
            setattr(self.p.scheme, pname, pvalue)

        self._iplot = None
        if not isinstance(self.p.scheme, Scheme):
            raise Exception("Provided scheme has to be a subclass"
                            + " of btplotting.schemes.scheme.Scheme")

        # when optreturn is active during optimization then we get
        # a thinned out result only
        self._is_optreturn = False
        self._current_fig_idx = None
        self.figurepages = {}
        # set tabs
        if not isinstance(self.p.tabs, list):
            raise Exception(
                "Param tabs needs to be a list containing tabs to display")
        if self.p.use_default_tabs:
            self.p.tabs = [AnalyzerTab, MetadataTab, LogTab] + self.p.tabs
        for tab in self.p.tabs:
            if not issubclass(tab, BacktraderPlottingTab):
                raise Exception(
                    "Tab needs to be a subclass of"
                    + " btplotting.tab.BacktraderPlottingTab")

    @property
    def _cur_figurepage(self):
        return self.figurepages[self._current_fig_id]

    @property
    def _cur_figurepage_id(self):
        return self._current_fig_id

    @_cur_figurepage_id.setter
    def _cur_figurepage_id(self, figid):
        if figid not in self.figurepages:
            raise RuntimeError(
                f'FigurePage with figid {figid} does not exist')
        self._current_fig_id = figid

    def _configure_plotting(self, strategy):
        '''
        Applies config from plotconfig param to objects
        '''
        datas = strategy.datas
        inds = strategy.getindicators()
        obs = strategy.getobservers()

        for objs in [datas, inds, obs]:
            for idx, obj in enumerate(objs):
                self._configure_plotobject(obj, idx, strategy)

    def _configure_plotobject(self, obj, idx, strategy):
        '''
        Applies config to a single object
        '''
        if self.p.plotconfig is None:
            return

        def apply_config(obj, config):
            for k, v in config.items():
                setattr(obj.plotinfo, k, v)

        for k, config in self.p.plotconfig.items():
            ctype, target = k.split(':')
            if ctype == 'r':  # regex
                label = obj2label(obj)
                m = re.match(target, label)
                if m:
                    apply_config(obj, config)
            elif ctype[0] == '#':  # index
                target_type, target_idx = target.split('-')
                # check if instance type matches
                if not isinstance(obj, FigureType.get_obj[target_type]):
                    continue
                if int(target_idx) != idx:
                    continue
                apply_config(obj, config)
            elif ctype == 'id':  # plotid
                plotid = getattr(obj.plotinfo, 'plotid', None)
                if plotid is None or plotid != target:
                    continue
                apply_config(obj, config)
            else:
                raise RuntimeError(
                    f'Unknown config type in plotting config: {k}')

    def _build_graph(self, strategy, datadomain=False):
        datas = strategy.datas
        inds = strategy.getindicators()
        obs = strategy.getobservers()
        data_graph = {}
        volume_graph = []
        for d in datas:
            if (not d.plotinfo.plot
                    or not filter_by_datadomain(d, datadomain)):
                continue

            pmaster = get_plotmaster(d.plotinfo.plotmaster)
            if pmaster is None:
                data_graph[d] = []
            else:
                if pmaster.plotinfo.plot:
                    if pmaster not in data_graph:
                        data_graph[pmaster] = []
                    data_graph[pmaster].append(d)

            if self.p.scheme.volume and self.p.scheme.voloverlay is False:
                volume_graph.append(d)

        for obj in itertools.chain(inds, obs):
            if not hasattr(obj, 'plotinfo'):
                # no plotting support cause no plotinfo attribute
                # available - so far LineSingle derived classes
                continue

            # should this indicator be plotted?
            if (not obj.plotinfo.plot
                    or obj.plotinfo.plotskip
                    or not filter_by_datadomain(obj, datadomain)):
                continue

            # subplot = create a new figure for this indicator
            subplot = obj.plotinfo.subplot
            pmaster = get_plotmaster(obj.plotinfo.plotmaster)
            if subplot and pmaster is None:
                data_graph[obj] = []
            else:
                if pmaster is None:
                    pmaster = get_plotmaster(get_indicator_data(obj))
                if pmaster not in data_graph:
                    data_graph[pmaster] = []
                data_graph[pmaster].append(obj)

        return data_graph, volume_graph

    def _test(self, strategy):
        from libs.btplotting.utils_new import get_dataname, get_clock_obj
        objs = list(itertools.chain(strategy.datas,
                                    strategy.getindicators(),
                                    strategy.getobservers()))
        for o in objs:
            if not isinstance(o, (bt.AbstractDataBase, bt.IndicatorBase, bt.ObserverBase)):
                continue
            print('OBJ', obj2label(o), get_dataname(o),
                  get_clock_obj(o))
            if hasattr(o, 'data'):
                print('HAS DATA', get_clock_obj(o.data))

    def _blueprint_strategy(self, strategy, datadomain=False):
        scheme = self.p.scheme
        strategy = self._cur_figurepage.strategy
        self._test(strategy)
        self._cur_figurepage.reset()
        self._cur_figurepage.analyzers += [
            a for _, a in strategy.analyzers.getitems()]

        data_graph, volume_graph = self._build_graph(
            strategy,
            datadomain=datadomain)

        # reset hover container to not mix hovers with other strategies
        hoverc = HoverContainer(
            hover_tooltip_config=scheme.hover_tooltip_config,
            is_multidata=len(strategy.datas) > 1)

        # set the cds for figurepage which contains all data
        cds = self._cur_figurepage.cds

        strat_figures = []
        for master, slaves in data_graph.items():
            plotorder = getattr(master.plotinfo, 'plotorder', 0)
            figure = Figure(
                cds=cds,
                hoverc=hoverc,
                scheme=scheme,
                master=master,
                slaves=slaves,
                plotorder=plotorder,
                is_multidata=len(strategy.datas) > 1)

            figure.plot(master)

            for s in slaves:
                figure.plot(s)
            strat_figures.append(figure)

        # apply legend configuration to figures
        for f in strat_figures:
            legend = f.figure.legend
            legend.click_policy = scheme.legend_click
            legend.location = scheme.legend_location
            legend.background_fill_color = scheme.legend_background_color
            legend.label_text_color = scheme.legend_text_color
            legend.orientation = scheme.legend_orientation

        # link axis
        for i in range(1, len(strat_figures)):
            strat_figures[i].figure.x_range = strat_figures[0].figure.x_range

        # apply hover tooltips
        hoverc.apply_hovertips(strat_figures)

        # add figures to figurepage
        self._cur_figurepage.figures += strat_figures

        # volume graphs
        for v in volume_graph:
            plotorder = getattr(v.plotinfo, 'plotorder', 0)
            figure = Figure(
                strategy=strategy,
                cds=cds,
                hoverc=hoverc,
                scheme=self.p.scheme,
                master=v,
                slaves=[],
                plotorder=plotorder,
                is_multidata=len(strategy.datas) > 1,
                type=FigureType.VOL)
            figure.plot_volume(v)
            self._cur_figurepage.figures.append(figure)

    def _blueprint_optreturn(self, optreturn):
        self._cur_figurepage.reset()
        self._cur_figurepage.analyzers += [
            a for _, a in optreturn.analyzers.getitems()]

    def _output_stylesheet(self, template="basic.css.j2"):
        return generate_stylesheet(self.p.scheme, template)

    def _output_plot_file(self, model, figid, filename=None,
                          template="basic.html.j2"):
        if filename is None:
            tmpdir = tempfile.gettempdir()
            filename = os.path.join(tmpdir, f"bt_bokeh_plot_{figid}.html")

        env = Environment(loader=PackageLoader('btplotting', 'templates'))
        templ = env.get_template(template)
        now = datetime.datetime.now()
        templ.globals['now'] = now.strftime("%Y-%m-%d %H:%M:%S")

        html = file_html(model,
                         template=templ,
                         resources=CDN,
                         template_variables=dict(
                             stylesheet=self._output_stylesheet(),
                             show_headline=self.p.scheme.show_headline))

        with open(filename, 'w') as f:
            f.write(html)

        return filename

    def _reset(self):
        self.figurepages = []
        self._is_optreturn = False

    def create_figurepage(self, obj, figid=0, start=None, end=None,
                          datadomain=False, filldata=True):
        '''
        Creates new FigurePage for given obj.
        The obj can be either an instance of bt.Strategy or bt.OptReturn
        '''
        fp = FigurePage(obj)
        self.figurepages[figid] = fp
        self._cur_figurepage_id = figid
        self._is_optreturn = isinstance(obj, bt.OptReturn)

        if isinstance(obj, bt.Strategy):
            self._configure_plotting(obj)
            self._blueprint_strategy(obj, datadomain=datadomain)
            if filldata:
                df = self.generate_data(start=start, end=end)
                self._cur_figurepage.set_data_from_df(df)
        elif isinstance(obj, bt.OptReturn):
            self._blueprint_optreturn(obj)
        else:
            raise Exception(
                f'Unsupported plot source object: {str(type(obj))}')
        return self._current_fig_id, self._cur_figurepage

    def update_figurepage(self, figid=0, datadomain=False):
        '''
        Updates the figurepage with the given figid
        '''
        self._cur_figurepage_id = figid
        fp = self._cur_figurepage
        if fp.strategy is not None:
            self._blueprint_strategy(
                fp.strategy,
                datadomain=datadomain)

    def generate_model(self, figid=0):
        '''
        Generates bokeh model used for the current figurepage
        '''
        self._cur_figurepage_id = figid
        fp = self._cur_figurepage

        if not self._is_optreturn:
            panels = self.generate_model_panels()
        else:
            panels = []

        for t in self.p.tabs:
            tab = t(self, fp, None)
            if tab.is_useable():
                panels.append(tab.get_panel())

        # set all tabs (filter out None)
        model = Tabs(tabs=list(filter(None.__ne__, panels)))
        # attach the model to the underlying figure for
        # later reference (e.g. unit test)
        fp.model = model

        return model

    def generate_model_panels(self):
        '''
        Generates bokeh panels used for current figurepage
        '''
        fp = self._cur_figurepage
        observers = [
            x for x in fp.figures
            if isinstance(x.master, bt.ObserverBase)]
        datas = [
            x for x in fp.figures
            if isinstance(x.master, bt.AbstractDataBase)]
        inds = [
            x for x in fp.figures
            if isinstance(x.master, bt.IndicatorBase)]

        # assign figures to tabs
        # 1. assign default tabs if no manual tab is assigned
        multiple_tabs = self.p.scheme.multiple_tabs
        for figure in [x for x in datas if x.plottab is None]:
            figure.plottab = 'Datas' if multiple_tabs else 'Plots'

        for figure in [x for x in inds if x.plottab is None]:
            figure.plottab = 'Indicators' if multiple_tabs else 'Plots'

        for figure in [x for x in observers if x.plottab is None]:
            figure.plottab = 'Observers' if multiple_tabs else 'Plots'

        # 2. group panels by desired tabs
        # groupby expects the groups to be sorted or else will produce
        # duplicated groups
        data_sort = {False: 0}
        sorted_figs = list(itertools.chain(datas, inds, observers))
        for i, d in enumerate(datas, start=1):
            data_sort[get_datadomain(d.master)] = i
        sorted_figs.sort(key=lambda x: (
            x.plotorder,
            data_sort[get_datadomain(x.master)],
            x.get_type().value))
        sorted_figs.sort(key=lambda x: x.plottab)
        tabgroups = itertools.groupby(sorted_figs, lambda x: x.plottab)

        panels = []
        for tabname, figures in tabgroups:
            figures = list(figures)
            if len(figures) == 0:
                continue
            # configure xaxis visibility
            if self.p.scheme.xaxis_pos == "bottom":
                for i, x in enumerate(figures):
                    x.figure.xaxis.visible = (
                        False if i < len(figures) - 1
                        else True)
            # create gridplot for panel
            g = gridplot([[x.figure] for x in figures],
                         toolbar_options={'logo': None},
                         toolbar_location=self.p.scheme.toolbar_location,
                         sizing_mode=self.p.scheme.plot_sizing_mode,
                         )
            # append created panel
            panels.append(Panel(title=tabname, child=g))

        return panels

    def generate_data(self, start=None, end=None, back=None,
                      preserveidx=False):
        '''
        Generates data for current figurepage
        '''
        fp = self._cur_figurepage
        objs = defaultdict(list)
        for f in fp.figures:
            dataname = get_dataname(f.master)
            objs[dataname].append(f.master)
            for s in f.slaves:
                objs[dataname].append(s)
        strategy = fp.strategy

        # use first data as clock
        smallest = False
        for k in objs.keys():
            if k is not False:
                smallest = k
                break

        # create clock values
        clock_values = {}
        # create the main clock for data alignment
        generator = ClockGenerator(strategy, smallest)
        clock_values[smallest] = generator.get_clock(
            start, end, back)
        clk, _, _ = clock_values[smallest]
        if len(clk) > 0:
            clkstart, clkend = clk[0], clk[-1]
            # ensure to reset end if no end is set, so we get also new
            # data for current candle
            if end is None:
                clkend = None
        else:
            clkstart, clkend = None, None
        # generate remaining clock values
        for k in objs.keys():
            if k not in clock_values and k is not False:
                generator = ClockGenerator(strategy, k)
                clock_values[k] = generator.get_clock(
                    clkstart, clkend)

        # generate clock handlers
        clocks = {}
        for name in clock_values:
            clk, clkstart, clkend = clock_values[name]
            clocks[name] = ClockHandler(clk, clkstart, clkend)
        # for objects not haivng a dataname, use smallest clock
        clocks[False] = clocks[smallest]

        # get the clock to use to align everything to
        clock = clocks[smallest]
        # get clock list for index
        clkidx = clock.clk

        # create index
        if preserveidx:
            idxstart = clock.start
            indices = list(range(idxstart, idxstart + len(clkidx)))
        else:
            indices = list(range(len(clkidx)))
        df = pd.DataFrame()
        df['datetime'] = clkidx
        df['index'] = indices

        # generate data for all figurepage objects
        for d in objs:
            for obj in objs[d]:
                tmpclk = clocks[get_datadomain(obj)]
                if isinstance(obj, bt.AbstractDataBase):
                    source_id = get_source_id(obj)
                    df_data = tmpclk.get_df_from_series(
                        obj, clkidx, source_id, ['datetime'])
                    df_colors = build_color_lines(
                        df_data,
                        self.p.scheme,
                        col_open=source_id + 'open',
                        col_close=source_id + 'close',
                        col_prefix=source_id)
                    df = df.join(df_data)
                    df = df.join(df_colors)
                else:
                    tmpclk = clocks[get_datadomain(obj)]
                    for lineidx, line in enumerate(obj.lines):
                        source_id = get_source_id(line)
                        new_line = tmpclk.get_list_from_line(line, clkidx)
                        df[source_id] = new_line

        # apply a proper index (should be identical to 'index' column)
        if df.shape[0] > 0:
            df.index = indices

        return df

    def plot_optmodel(self, obj):
        self._reset()
        self.plot(obj)

        # we support only one strategy at a time so pass fixed zero index
        # if we ran optresults=False then we have a full strategy object
        # -> pass it to get full plot
        return self.generate_model(0)

    def plot(self, obj, figid=0, numfigs=1, iplot=True, start=None,
             end=None, use=None, datadomain=False, **kwargs):
        '''
        Plot either a strategy or an optimization result
        This method is called by backtrader
        '''
        if numfigs > 1:
            raise Exception("numfigs must be 1")
        if use is not None:
            raise Exception("Different backends by 'use' not supported")

        self._iplot = iplot and 'ipykernel' in sys.modules

        # create figurepage for obj
        self.create_figurepage(
            obj,
            figid=figid,
            start=start,
            end=end,
            datadomain=datadomain)

        # returns all figurepages
        return self.figurepages

    def show(self):
        '''
        Display a figure
        This method is called by backtrader
        '''
        for figid in self.figurepages:
            model = self.generate_model(figid)

            if self.p.output_mode in ['show', 'save']:
                if self._iplot:
                    css = self._output_stylesheet()
                    display(HTML(css))
                    show(model)
                else:
                    filename = self._output_plot_file(
                        model, figid, self.p.filename)
                    if self.p.output_mode == 'show':
                        view(filename)
            elif self.p.output_mode == 'memory':
                pass
            else:
                raise RuntimeError(
                    f'Invalid parameter "output_mode"'
                    + ' with value: {self.p.output_mode}')

        self._reset()
