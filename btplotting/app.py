from copy import copy
from collections import defaultdict
from datetime import datetime
import logging
import re
import os
import sys
import tempfile

import backtrader as bt

import pandas as pd

from bokeh.models import TabPanel, Tabs, InlineStyleSheet
from bokeh.layouts import gridplot, column

from bokeh.embed import file_html
from bokeh.resources import CDN, Resources

from bokeh.util.browser import view
from bokeh.io import show
from bokeh.io.export import get_screenshot_as_png

from jinja2 import Environment, PackageLoader

from .schemes import Scheme, Blackly

from .utils import get_dataname, get_datanames, \
    get_plotobjs, filter_obj
from .figure import FigurePage, FigureType, Figure
from .clock import DataClockHandler
from .helper.label import obj2label
from .helper.bokeh import generate_stylesheet
from .tab import BacktraderPlottingTab
from .tabs import AnalyzerTab, MetadataTab, LogTab, SourceTab

if 'ipykernel' in sys.modules:
    from IPython.core.display import display, HTML

_logger = logging.getLogger(__name__)


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
        # default filterdata to apply on plots
        ('filterdata', None),
    )

    def __init__(self, **kwargs):
        if not isinstance(self.p.scheme, Scheme):
            raise Exception('Provided scheme has to be a subclass'
                            ' of btplotting.schemes.scheme.Scheme')
        # set new scheme instance for app, so source scheme
        # remains untouched
        self.scheme = copy(self.p.scheme)
        # store css stylesheet for bokeh styling
        self.stylesheet = InlineStyleSheet(
            css=generate_stylesheet(self.scheme, 'bokeh.css.j2'))
        # apply additional parameters to override / set scheme settings
        for pname, pvalue in kwargs.items():
            setattr(self.scheme, pname, pvalue)

        self._iplot = None
        self._figurepages = {}
        # set tabs
        self.tabs = copy(self.p.tabs)
        if self.p.use_default_tabs:
            self.tabs += [
                AnalyzerTab, MetadataTab, SourceTab, LogTab]
        if not isinstance(self.tabs, list):
            raise Exception(
                'Param tabs needs to be a list containing tabs to display')
        for tab in self.tabs:
            if not issubclass(tab, BacktraderPlottingTab):
                raise Exception(
                    'Tab needs to be a subclass of'
                    ' btplotting.tab.BacktraderPlottingTab')

    def _reset(self):
        '''
        Resets the app
        '''
        self._figurepages = {}

    def _configure_plotting(self, figid=0):
        '''
        Applies config from plotconfig param to objects
        '''
        fp = self.get_figurepage(figid)
        objs = get_plotobjs(fp.strategy, include_non_plotable=True)

        i = 0
        for d in objs:
            if not isinstance(d, bt.Strategy):
                self._configure_plotobj(d, i)
                i += 1
            for s in objs[d]:
                self._configure_plotobj(s, i)
                i += 1

    def _configure_plotobj(self, obj, idx):
        '''
        Applies config to a single object
        '''

        # patch every object to contain plotorder and plotid
        if not hasattr(obj.plotinfo, 'plotid'):
            obj.plotinfo.plotid = f'{FigureType.get_type(obj).name}{idx}'
        if not hasattr(obj.plotinfo, 'plotorder'):
            obj.plotinfo.plotorder = 0

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
                plotid = obj.plotinfo.plotid
                if plotid is None or plotid != target:
                    continue
                apply_config(obj, config)
            elif ctype == 'name':  # name
                label = obj2label(obj)
                if not label.contains(target):
                    continue
                apply_config(obj, config)
            else:
                raise RuntimeError(
                    f'Unknown config type in plotting config: {k}')

    def _get_plotobjs(self, figid=0, filterdata=None):
        '''
        Returns a filtered dict of objects to be plotted
        '''
        fp = self.get_figurepage(figid)
        objs = get_plotobjs(fp.strategy, order_by_plotmaster=True)
        filtered = {}
        for o in objs:
            if filter_obj(o, filterdata):
                continue
            childs = []
            for c in objs[o]:
                if not filter_obj(c, filterdata):
                    childs.append(c)
            filtered[o] = childs
        return filtered

    def _blueprint_strategy(self, figid=0, filterdata=None):
        '''
        Fills a FigurePage with Figures of all objects to be plotted
        '''
        fp = self.get_figurepage(figid)
        strategy = fp.strategy
        scheme = self.scheme
        fp.reset()
        fp.analyzers += [a for _, a in fp.strategy.analyzers.getitems()]

        # store data clock in figurepage
        dataname = False
        for i in get_datanames(strategy, True):
            dataname = i
            if not filter_obj(strategy.getdatabyname(i), filterdata):
                break
        fp.data_clock = DataClockHandler(strategy, dataname)

        # get the objects to be plotted
        objs = self._get_plotobjs(figid, filterdata)

        # create figures
        figures = []
        for parent, childs in objs.items():
            figure = Figure(
                fp=fp,
                scheme=scheme,
                master=parent,
                childs=childs)
            figure.plot(parent)
            for c in childs:
                figure.plot(c)
            figure.apply()
            figures.append(figure)

        # link axis
        for i in range(1, len(figures)):
            figures[i].figure.x_range = figures[0].figure.x_range

        # add figures to figurepage
        fp.figures += figures

        # volume figures
        if self.scheme.volume and self.scheme.voloverlay is False:
            for f in figures:
                if not f.get_type() == FigureType.DATA:
                    continue
                figure = Figure(
                    fp=fp,
                    scheme=scheme,
                    master=f.master,
                    childs=[],
                    type=FigureType.VOL)
                figure.plot_volume(f.master)
                figure.apply()
                fp.figures.append(figure)

        # apply all figurepage related functionality after all figures
        # are set
        fp.apply()

    def _blueprint_optreturn(self, figid=0):
        '''
        Fills a FigurePage with all objects from optimization process
        '''
        fp = self.get_figurepage(figid)
        optreturn = fp.optreturn
        fp.reset()
        fp.analyzers += [
            a for _, a in optreturn.analyzers.getitems()]

    def _output_stylesheet(self, template='basic.css.j2'):
        '''
        Renders and returns the stylesheet
        '''
        return generate_stylesheet(self.scheme, template)

    def _output_plotfile(self, model, figid=0, filename=None,
                         template='basic.html.j2'):
        '''
        Outputs the plot file
        '''
        if filename is None:
            tmpdir = tempfile.gettempdir()
            filename = os.path.join(tmpdir, f'bt_bokeh_plot_{figid}.html')

        now = datetime.now()
        env = Environment(loader=PackageLoader('btplotting', 'templates'))
        templ = env.get_template(template)
        templ.globals['now'] = now.strftime('%Y-%m-%d %H:%M:%S')

        html = file_html(model,
                         template=templ,
                         resources=CDN,
                         template_variables=dict(
                             stylesheet=self._output_stylesheet(),
                             show_headline=self.scheme.show_headline,
                             headline=self.scheme.headline),
                         _always_new=True)

        with open(filename, 'w') as f:
            f.write(html)

        return filename

    def create_figurepage(self, obj, figid=0, start=None, end=None,
                          filterdata=None, filldata=True):
        '''
        Creates new FigurePage for given obj.
        The obj can be either an instance of bt.Strategy or bt.OptReturn
        '''
        fp = FigurePage(obj, self.scheme)
        if figid in self._figurepages:
            raise Exception(f'FigurePage with figid "{figid}" already exists')
        self._figurepages[figid] = fp

        if isinstance(obj, bt.Strategy):
            self._configure_plotting(figid)
            self._blueprint_strategy(figid, filterdata)
            if filldata:
                df = self.get_data(figid, start=start, end=end)
                fp.set_cds_columns_from_df(df)
        elif isinstance(obj, bt.OptReturn):
            self._blueprint_optreturn(figid)
        else:
            raise Exception(
                f'Unsupported plot source object: {str(type(obj))}')
        return figid, fp

    def update_figurepage(self, figid=0, filterdata=None):
        '''
        Updates the figurepage with the given figid
        '''
        self._blueprint_strategy(figid, filterdata)

    def get_figurepage(self, figid=0):
        '''
        Returns the FigurePage with the given figid
        '''
        if figid not in self._figurepages:
            raise Exception(f'FigurePage with figid "{figid}" does not exist')
        return self._figurepages[figid]

    def generate_bokeh_model(self, figid=0, use_tabs=True):
        '''
        Generates bokeh model used for the current figurepage
        '''
        fp = self.get_figurepage(figid)
        if use_tabs:
            if fp.strategy is not None:
                tab_panels = self.generate_bokeh_model_tab_panels()
            else:
                tab_panels = []

            for t in self.tabs:
                tab = t(self, fp, None)
                if tab.is_useable():
                    tab_panels.append(tab.get_tab_panel())
            # set all tabs (filter out None)
            all_tabs = list(filter(None.__ne__, tab_panels))
            model = Tabs(tabs=all_tabs, sizing_mode='stretch_width')
        else:
            model = self.generate_bokeh_model_plots()
        # attach the model to the underlying figure for
        # later reference (e.g. unit test)
        fp.model = model

        return model

    def generate_bokeh_model_tab_panels(self, figid=0):
        '''
        Generates bokeh tab panels used for figurepage
        '''
        fp = self.get_figurepage(figid)

        # sort figures
        data_sort = {False: 0}
        for i, d in enumerate(
                get_datanames(fp.strategy, onlyplotable=False),
                start=1):
            data_sort[d] = i
        sorted_figs = list(fp.figures)
        sorted_figs.sort(key=lambda x: (
            x.get_plotorder(),
            data_sort[get_dataname(x.master)],
            x.get_type().value))

        # fill tabs
        multiple_tabs = self.scheme.multiple_tabs
        tabs = defaultdict(list)
        for f in sorted_figs:
            tab = f.get_plottab()
            if tab:
                tabs[tab].append(f)
            elif not multiple_tabs:
                tabs['Plots'].append(f)
            else:
                figtype = f.get_type()
                if figtype == FigureType.DATA:
                    tabs['Datas'].append(f)
                elif figtype == FigureType.OBS:
                    tabs['Observers'].append(f)
                elif figtype == FigureType.IND:
                    tabs['Indicators'].append(f)
                else:
                    raise Exception(f'Unknown FigureType "{figtype}"')

        # create tab panels for tabs
        tab_panels = []
        for tab in tabs:
            if len(tabs[tab]) == 0:
                continue
            # configure xaxis visibility
            if self.scheme.xaxis_pos == 'bottom':
                for i, x in enumerate(tabs[tab]):
                    x.figure.xaxis.visible = (
                        False if i < len(tabs[tab]) - 1
                        else True)
            # create gridplot for tab panel
            plot_figures = [[x.figure] for x in tabs[tab]]
            g = gridplot(plot_figures,
                         sizing_mode='stretch_width',
                         merge_tools=False,
                         toolbar_options={'logo': None, 'autohide': True},
                         toolbar_location=self.scheme.toolbar_location,)
            # append created tab panel
            tab_panels.append(TabPanel(title=tab, child=g))

        return tab_panels

    def generate_bokeh_model_plots(self, figid=0):
        '''
        Generates bokeh plots used for figurepage
        '''
        fp = self.get_figurepage(figid)

        # sort figures
        data_sort = {False: 0}
        for i, d in enumerate(
                get_datanames(fp.strategy, onlyplotable=False),
                start=1):
            data_sort[d] = i
        sorted_figs = list(fp.figures)
        for f in sorted_figs:
            f.figure.toolbar.logo = None
            f.figure.toolbar_location = None
        sorted_figs.sort(key=lambda x: (
            x.get_plotorder(),
            data_sort[get_dataname(x.master)],
            x.get_type().value))
        all_figures = [x.figure for x in sorted_figs]
        return column(all_figures)

    def get_data(self, figid=0, startidx=None, start=None, end=None, back=None):
        '''
        Returns data for given figurepage
        '''
        fp = self.get_figurepage(figid)
        data_clock: DataClockHandler = fp.data_clock
        data_clock.init_clk()

        if startidx:
            assert start is None, "wrong"
            start = data_clock.get_dt_at_idx(startidx)

        # only start_idx, end_idx should be used so all data
        # is aligned to the same clock length.
        # clk = data_clock._get_clk()
        startidx, endidx = data_clock.get_start_end_idx(start, end, back)
        # create datetime column
        dt_idx = data_clock.get_dt_list(startidx, endidx)
        # create index column
        int_idx = data_clock.get_idx_list(startidx, endidx)
        assert startidx == int_idx[0] and endidx == int_idx[-1], "wrong"
        # create dataframe with datetime and prepared index
        # the index will be applied at the end after data is
        # set
        df = pd.DataFrame(
            data={
                'index': pd.Series(int_idx, dtype='int64'),
                'datetime': pd.Series(dt_idx, dtype='datetime64[ns]')})
        # generate data for all figurepage objects
        df_objs = []
        for f in fp.figures:
            fillnan = f.fillnan()
            skipnan = f.skipnan()
            for obj in [f.master] + f.childs:
                df_data = data_clock.get_data(
                    obj, startidx, endidx,
                    fillnan=fillnan,
                    skipnan=skipnan)
                df_objs.append(df_data)
        df = df.join(df_objs)
        # set index and return dataframe
        data_clock.uinit_clk(endidx)
        return df

    def get_last_idx(self, figid=0):
        '''
        Returns the last index of figurepage data
        '''
        fp = self.get_figurepage(figid)
        # return len(fp.data_clock) - 1
        return fp.data_clock.last_endidx

    def is_iplot(self):
        '''
        Returns iplot value
        '''
        return self._iplot

    def plot_optmodel(self, obj):
        '''
        Plots a optimization model
        '''
        self._reset()
        self.plot(obj)

        # we support only one strategy at a time so pass fixed zero index
        # if we ran optresults=False then we have a full strategy object
        # -> pass it to get full plot
        return self.generate_bokeh_model(0)

    def plot(self, obj, figid=0, numfigs=1, iplot=True, start=None,
             end=None, use=None, filterdata=None, **kwargs):
        '''
        Plot either a strategy or an optimization result
        This method is called by backtrader

        src:
        https://stackoverflow.com/questions/44100477/how-to-check-if-you-are-in-a-jupyter-notebook
        '''
        if numfigs > 1:
            raise Exception('numfigs must be 1')
        if use is not None:
            raise Exception('Different backends by "use" not supported')

        if iplot:
            try:
                get_ipython  # noqa: *
                self._iplot = True
            except NameError:
                pass

        if not filterdata:
            filterdata = self.p.filterdata

        # create figurepage for obj
        self.create_figurepage(
            obj,
            figid=figid,
            start=start,
            end=end,
            filterdata=filterdata)

        # returns all figurepages
        return self._figurepages

    def show(self):
        '''
        Display a figure
        This method is called by backtrader
        '''
        for figid in self._figurepages:
            model = self.generate_bokeh_model(figid)

            if self.p.output_mode in ['show', 'save']:
                if self._iplot:
                    css = self._output_stylesheet()
                    display(HTML(css))
                    show(model)
                else:
                    filename = self._output_plotfile(
                        model, figid, self.p.filename)
                    if self.p.output_mode == 'show':
                        view(filename)
            elif self.p.output_mode == 'memory':
                pass
            else:
                raise RuntimeError(
                    'Invalid parameter "output_mode"'
                    + f' with value: {self.p.output_mode}')

    def save_png(self, obj, figid=0, start=None, end=None,
                 filterdata=None, filename='out.png', driver=None,
                 timeout=5):
        if not filterdata:
            filterdata = self.p.filterdata
        # create figurepage for obj
        self.create_figurepage(
            obj,
            figid=figid,
            start=start,
            end=end,
            filterdata=filterdata)
        # create and export model
        model = self.generate_bokeh_model(figid, use_tabs=False)
        resources = Resources()
        resources.css_raw.append(self._output_stylesheet())
        image = get_screenshot_as_png(
            model,
            driver=driver,
            timeout=timeout,
            resources=resources)
        if image.width != 0 and image.height != 0:
            image.save(filename)
