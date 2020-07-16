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

from .utils import find_by_plotid, get_indicator_data, \
    get_datadomain, filter_by_datadomain, get_source_id
from .figure import FigurePage, FigureType, Figure, HoverContainer
from .clock import ClockGenerator, ClockHandler
from .helper.label_resolver import plotobj2label
from .helper.bokeh import generate_stylesheet, build_color_lines, \
    sort_plotobjects, get_plotmaster
from .tabs import get_analyzer_panel, get_metadata_panel, \
    get_log_panel
from .tabs.log import is_log_tab_initialized

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
    -these examples should work:
      * https://www.backtrader.com/blog/posts/2015-09-21-plotting-same-axis/plotting-same-axis/
      * https://www.backtrader.com/docu/plotting/sameaxis/plot-sameaxis/
    -data generation based on figurepage (build_data should not care about datadomain)
    -datadomain should be cleaned up (provide one or more datadomains)
    -should be able to add additional tabs
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
    )

    def __init__(self, **kwargs):
        # apply additional parameters to override / set scheme settings
        for pname, pvalue in kwargs.items():
            setattr(self.p.scheme, pname, pvalue)

        self._iplot = None
        if not isinstance(self.p.scheme, Scheme):
            raise Exception("Provided scheme has to be a subclass" +
                            " of btplotting.schemes.scheme.Scheme")

        # when optreturn is active during optimization then we get
        # a thinned out result only
        self._is_optreturn = False
        self._current_fig_idx = None
        self.figurepages = []

    def _configure_plotting(self, strategy):
        datas = strategy.datas
        inds = strategy.getindicators()
        obs = strategy.getobservers()

        for objs in [datas, inds, obs]:
            for idx, obj in enumerate(objs):
                self._configure_plotobject(obj, idx, strategy)

    def _configure_plotobject(self, obj, idx, strategy):
        if self.p.plotconfig is None:
            return

        def apply_config(obj, config):
            for k, v in config.items():
                if k == 'plotmaster':
                    # this needs special treatment since a string
                    # is passed but we need to set the actual obj
                    v = find_by_plotid(strategy, v)
                setattr(obj.plotinfo, k, v)

        for k, config in self.p.plotconfig.items():
            ctype, target = k.split(':')

            if ctype == 'r':  # regex
                label = plotobj2label(obj)

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
            plotmaster = obj.plotinfo.plotmaster
            if subplot and plotmaster is None:
                data_graph[obj] = []
            else:
                plotmaster = (plotmaster
                              if plotmaster is not None
                              else get_indicator_data(obj))

                if plotmaster not in data_graph:
                    data_graph[plotmaster] = []
                data_graph[plotmaster].append(obj)

        return data_graph, volume_graph

    def _blueprint_strategy(self, strategy, datadomain=False):

        self._cur_figurepage.reset()
        self._cur_figurepage.analyzers += [a for _,
                                          a in strategy.analyzers.getitems()]

        data_graph, volume_graph = self._build_graph(strategy, datadomain)

        # reset hover container to not mix hovers with other strategies
        hoverc = HoverContainer(
            hover_tooltip_config=self.p.scheme.hover_tooltip_config,
            is_multidata=len(strategy.datas) > 1)

        # set the cds for figurepage which contains all data
        cds = self._cur_figurepage.cds

        strat_figures = []
        for master, slaves in data_graph.items():
            plotorder = getattr(master.plotinfo, 'plotorder', 0)
            figure = Figure(
                strategy=strategy,
                cds=cds,
                hoverc=hoverc,
                scheme=self.p.scheme,
                master=master,
                plotorder=plotorder,
                is_multidata=len(strategy.datas) > 1)

            figure.plot(master, None)

            for s in slaves:
                figure.plot(s, master)
            strat_figures.append(figure)

        # apply legend configuration to figures
        for f in strat_figures:
            f.figure.legend.click_policy = self.p.scheme.legend_click
            f.figure.legend.location = self.p.scheme.legend_location
            f.figure.legend.background_fill_color = self.p.scheme.legend_background_color
            f.figure.legend.label_text_color = self.p.scheme.legend_text_color
            f.figure.legend.orientation = self.p.scheme.legend_orientation

        # link axis
        for i in range(1, len(strat_figures)):
            strat_figures[i].figure.x_range = strat_figures[0].figure.x_range

        # configure xaxis visibility
        if self.p.scheme.xaxis_pos == "bottom":
            for i, f in enumerate(strat_figures):
                f.figure.xaxis.visible = (
                    False if i < len(strat_figures) - 1
                    else True)

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
                plotorder=plotorder,
                is_multidata=len(strategy.datas) > 1,
                type=FigureType.VOL)
            figure.plot_volume(v)
            self._cur_figurepage.figures.append(figure)

    def _blueprint_optreturn(self, optreturn):
        self._cur_figurepage.reset()
        self._cur_figurepage.analyzers += [
            a for _, a
            in optreturn.analyzers.getitems()]

    def _reset(self):
        self.figurepages = []
        self._is_optreturn = False

    @property
    def _cur_figurepage(self):
        return self.figurepages[self._current_fig_idx]

    @property
    def is_tabs_single(self):
        if self.p.scheme.tabs == 'single':
            return True
        elif self.p.scheme.tabs == 'multi':
            return False
        else:
            raise RuntimeError(
                f'Invalid tabs parameter "{self.p.scheme.tabs}"')

    def get_figurepage(self, idx=0):
        return self.figurepages[idx]

    def create_figurepage(self, obj, start=None, end=None, datadomain=False,
                          filldata=True):
        '''
        Creates new FigurePage for given obj.
        The obj can be either an instance of bt.Strategy or bt.OptReturn
        '''

        fp = FigurePage(obj)
        self.figurepages.append(fp)
        self._current_fig_idx = len(self.figurepages) - 1
        self._is_optreturn = isinstance(obj, bt.OptReturn)

        if isinstance(obj, bt.Strategy):
            self._configure_plotting(obj)
            self._blueprint_strategy(obj, datadomain)
            if filldata:
                df = self.build_data(
                    strategy=obj,
                    start=start,
                    end=end,
                    datadomain=datadomain)
                self._cur_figurepage.set_data_from_df(df)
        elif isinstance(obj, bt.OptReturn):
            self._blueprint_optreturn(obj)
        else:
            raise Exception(
                f'Unsupported plot source object: {str(type(obj))}')
        return self._current_fig_idx, self._cur_figurepage

    def update_figurepage(self, idx=0, datadomain=False):
        self._current_fig_idx = idx
        if self._cur_figurepage.strategy is not None:
            self._blueprint_strategy(self._cur_figurepage.strategy, datadomain)

    def generate_model(self, figurepage_idx=0):
        if figurepage_idx >= len(self.figurepages):
            raise RuntimeError(
                'Cannot generate model for FigurePage'
                + f'with index {figurepage_idx} as there are only'
                + f' {len(self.figurepages)}.')

        figurepage = self.figurepages[figurepage_idx]

        if not self._is_optreturn:
            panels = self.generate_model_panels(figurepage)
        else:
            panels = []

        # append analyzer panel
        panel_analyzer = get_analyzer_panel(self, figurepage, None)
        panels.append(panel_analyzer)

        # append meta panel
        if not self._is_optreturn:
            assert figurepage.strategy is not None
            panel_metadata = get_metadata_panel(self, figurepage, None)
            panels.append(panel_metadata)

        # append log panel
        if is_log_tab_initialized():
            panel_log = get_log_panel(self, figurepage, None)
            panels.append(panel_log)

        # set all tabs (filter out None)
        model = Tabs(tabs=list(filter(None.__ne__, panels)))

        # attach the model to the underlying figure for
        # later reference (e.g. unit test)
        figurepage.model = model

        return model

    def generate_model_panels(self, fp, datadomain=False):
        observers = [
            x for x in fp.figures
            if isinstance(x.master, bt.ObserverBase)]
        datas = [
            x for x in fp.figures
            if isinstance(x.master, bt.AbstractDataBase)]
        inds = [
            x for x in fp.figures
            if isinstance(x.master, bt.IndicatorBase)]

        # now assign figures to tabs
        # 1. assign default tabs if no manual tab is assigned
        for figure in [x for x in datas if x.plottab is None]:
            figure.plottab = 'Plots' if self.is_tabs_single else 'Datas'

        for figure in [x for x in inds if x.plottab is None]:
            figure.plottab = 'Plots' if self.is_tabs_single else 'Indicators'

        for figure in [x for x in observers if x.plottab is None]:
            figure.plottab = 'Plots' if self.is_tabs_single else 'Observers'

        # 2. group panels by desired tabs
        # groupby expects the groups to be sorted or else will produce
        # duplicated groups
        sorted_figs = list(itertools.chain(datas, inds, observers))

        # 3. filter datadomains
        if datadomain is not False:
            filtered = []
            for f in sorted_figs:
                lgs = f.get_datadomains()
                for lg in lgs:
                    if lg is True or lg == datadomain:
                        filtered.append(f)
            sorted_figs = filtered

        # 4. sort figures by plotorder, datadomain and type
        data_sort = {False: 0}
        for i, d in enumerate(datas, start=1):
            data_sort[get_datadomain(d.master)] = i
        sorted_figs.sort(key=lambda x: (
            x.plotorder, data_sort[x.get_datadomain()], x.get_type().value))
        sorted_figs.sort(key=lambda x: x.plottab)
        tabgroups = itertools.groupby(sorted_figs, lambda x: x.plottab)

        panels = []

        def build_panel(objects, panel_title):
            if len(objects) == 0:
                return

            sort_plotobjects(objects)

            g = gridplot([[x.figure] for x in objects],
                         toolbar_options={'logo': None},
                         toolbar_location=self.p.scheme.toolbar_location,
                         sizing_mode=self.p.scheme.plot_sizing_mode,
                         )
            panels.append(Panel(title=panel_title, child=g))

        for tabname, figures in tabgroups:
            build_panel(list(figures), tabname)

        return panels

    def _output_stylesheet(self, template="basic.css.j2"):
        return generate_stylesheet(self.p.scheme, template)

    def _output_plot_file(
            self,
            model, idx,
            filename=None,
            template="basic.html.j2"):
        if filename is None:
            tmpdir = tempfile.gettempdir()
            filename = os.path.join(tmpdir, f"bt_bokeh_plot_{idx}.html")

        env = Environment(loader=PackageLoader('btplotting', 'templates'))
        templ = env.get_template(template)
        now = datetime.datetime.now()
        templ.globals['now'] = now.strftime("%Y-%m-%d %H:%M:%S")

        html = file_html(model,
                         template=templ,
                         resources=CDN,
                         template_variables=dict(
                             stylesheet=self._output_stylesheet(),
                             show_headline=self.p.scheme.show_headline,
                         )
                        )

        with open(filename, 'w') as f:
            f.write(html)

        return filename

    def savefig(self, fig, filename, width, height, dpi, tight):
        self._generate_output(fig, filename)

    def list_datadomains(self, strategy):
        datadomains = []
        for d in strategy.datas:
            datadomains.append(get_datadomain(d))
        return datadomains

    def get_last_idx(self, strategy, datadomain=False):
        if datadomain is not False:
            data = strategy.getdatabyname(datadomain)
            return len(data) - 1
        return len(strategy) - 1

    def get_clock_generator(self, strategy, datadomain=False):
        if datadomain is not False:
            data = strategy.getdatabyname(datadomain)
            return ClockGenerator(data.datetime, data._tz)
        return ClockGenerator(strategy.datetime, strategy.datas[0]._tz)

    def build_data(self, strategy, start=None, end=None, back=None,
                   datadomain=False, preserveidx=False):

        clock_values = {}
        # create the main clock for data alignment
        generator = self.get_clock_generator(strategy, datadomain)
        clock_values[datadomain] = generator.get_clock(
            start, end, back)
        # get start and end values from main clock
        clk, _, _ = clock_values[datadomain]
        if len(clk) > 0:
            clkstart, clkend = clk[0], clk[-1]
            if end is None:
                clkend = None
        else:
            clkstart, clkend = None, None

        # generate additional clocks
        if datadomain is not False:
            # ensure we have strategies clock if a datadomain is set
            generator = self.get_clock_generator(strategy)
            clock_values[False] = generator.get_clock(
                clkstart, clkend)
        for data in strategy.datas:
            if datadomain is False or data._name != datadomain:
                generator = self.get_clock_generator(strategy, data._name)
                clock_values[data._name] = generator.get_clock(
                    clkstart, clkend)

        clocks = {}
        # generate clock handlers
        for name in clock_values:
            clk, clkstart, clkend = clock_values[name]
            clocks[name] = ClockHandler(clk, clkstart, clkend)

        # get the clock to use to align everything to
        clock = clocks[datadomain]
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

        # append data columns
        for data in strategy.datas:
            if filter_by_datadomain(data, datadomain):
                tmpclk = clocks[get_datadomain(data)]
                source_id = get_source_id(data)
                df_data = tmpclk.get_df_from_series(data, clkidx, source_id)
                df = df.join(df_data)
                df_colors = build_color_lines(
                    df_data,
                    self.p.scheme,
                    col_open=source_id + 'open',
                    col_close=source_id + 'close',
                    col_prefix=source_id)
                df = df.join(df_colors)

        # append obs and ind columns
        for obj in itertools.chain(
                strategy.getindicators(),
                strategy.getobservers()):
            if filter_by_datadomain(obj, datadomain):
                tmpclk = clocks[get_datadomain(obj)]
                num_lines = obj.size() if getattr(obj, 'size', None) else 1
                for lineidx in range(num_lines):
                    line = obj.lines[lineidx]
                    source_id = get_source_id(line)
                    new_line = tmpclk.get_list_from_line(line, clkidx)
                    df[source_id] = new_line

        # apply a proper index (should be identical to 'index' column)
        if df.shape[0] > 0:
            df.index = indices

        return df

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
            start=start,
            end=end,
            datadomain=datadomain)

        # returns all figurepages
        return self.figurepages

    def plot_optmodel(self, obj):
        self._reset()
        self.plot(obj)

        # we support only one strategy at a time so pass fixed zero index
        # if we ran optresults=False then we have a full strategy object
        # -> pass it to get full plot
        return self.generate_model(0)

    def show(self):
        '''
        Display a figure
        This method is called by backtrader
        '''

        for idx in range(len(self.figurepages)):
            model = self.generate_model(idx)

            if self.p.output_mode in ['show', 'save']:
                if self._iplot:
                    css = self._output_stylesheet()
                    display(HTML(css))
                    show(model)
                else:
                    filename = self._output_plot_file(
                        model,
                        idx,
                        self.p.filename)
                    if self.p.output_mode == 'show':
                        view(filename)
            elif self.p.output_mode == 'memory':
                pass
            else:
                raise RuntimeError(
                    f'Invalid parameter "output_mode"'
                    + ' with value: {self.p.output_mode}')

        self._reset()
