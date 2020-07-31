import logging
from functools import partial

from bokeh.layouts import column, row, layout
from bokeh.models import Select, Spacer, Tabs, Button

from .datahandler import LiveDataHandler
from ..tabs import ConfigTab
from ..utils import get_datanames

_logger = logging.getLogger(__name__)


class LiveClient:

    '''
    LiveClient provides live plotting functionality.
    '''

    NAV_BUTTON_WIDTH = 38

    def __init__(self, doc, app, strategy, lookback):
        self._app = app
        self._strategy = strategy
        self._refresh_fnc = None
        self._datahandler = None
        self._figurepage = None
        self._paused = False
        self._filter = ''
        # plotgroup for filter
        self.plotgroup = ''
        # amount of candles to plot
        self.lookback = lookback
        # should gaps in data be filled
        self.fill_gaps = False
        # bokeh document for client
        self.doc = doc
        # model is the root model for bokeh and will be set in baseapp
        self.model = None

        # append config tab if default tabs should be added
        if self._app.p.use_default_tabs:
            self._app.tabs.append(ConfigTab)
        # set plotgroup from app params if provided
        if self._app.p.filter and self._app.p.filter['group']:
            self.plotgroup = self._app.p.filter['group']
        # create figurepage
        self._figid, self._figurepage = self._app.create_figurepage(
            self._strategy, filldata=False)
        # create model
        self.model, self._refresh_fnc = self._createmodel()
        # update model with current figurepage
        self.updatemodel()

    def _createmodel(self):

        def on_select_filter(self, a, old, new):
            _logger.debug(f'Switching filter to {new}...')
            # ensure datahandler is stopped
            self._datahandler.stop()
            self._filter = new
            self.updatemodel()
            _logger.debug('Switching filter finished')

        def on_click_nav_action(self):
            if not self._paused:
                self._pause()
            else:
                self._resume()
            refresh(self)

        def on_click_nav_prev(self, steps=1):
            self._pause()
            self._set_data_by_idx(self._datahandler.get_last_idx() - steps)
            update_nav_buttons(self)

        def on_click_nav_next(self, steps=1):
            self._pause()
            self._set_data_by_idx(self._datahandler.get_last_idx() + steps)
            update_nav_buttons(self)

        def refresh(self):
            self.doc.add_next_tick_callback(partial(update_nav_buttons, self))

        def reset_nav_buttons(self):
            btn_nav_prev.disabled = True
            btn_nav_next.disabled = True
            btn_nav_action.label = '❙❙'

        def update_nav_buttons(self):
            last_idx = self._datahandler.get_last_idx()
            last_avail_idx = self._app.get_last_idx(self._figid)

            if last_idx < self.lookback:
                btn_nav_prev.disabled = True
                btn_nav_prev_big.disabled = True
            else:
                btn_nav_prev.disabled = False
                btn_nav_prev_big.disabled = False
            if last_idx >= last_avail_idx:
                btn_nav_next.disabled = True
                btn_nav_next_big.disabled = True
            else:
                btn_nav_next.disabled = False
                btn_nav_next_big.disabled = False
            if self._paused:
                btn_nav_action.label = '▶'
            else:
                btn_nav_action.label = '❙❙'

        # filter selection
        datanames = get_datanames(self._strategy)
        options = [('', 'Strategy')]
        for d in datanames:
            options.append(('D' + d, f'Data: {d}'))
        options.append(('G', 'Plot Group'))
        self._filter = 'D' + datanames[0]
        select_filter = Select(
            value=self._filter,
            options=options)
        select_filter.on_change(
            'value',
            partial(on_select_filter, self))
        # nav
        btn_nav_prev = Button(label='❮', width=self.NAV_BUTTON_WIDTH)
        btn_nav_prev.on_click(partial(on_click_nav_prev, self))
        btn_nav_prev_big = Button(label='❮❮', width=self.NAV_BUTTON_WIDTH)
        btn_nav_prev_big.on_click(partial(on_click_nav_prev, self, 10))
        btn_nav_action = Button(label='❙❙', width=self.NAV_BUTTON_WIDTH)
        btn_nav_action.on_click(partial(on_click_nav_action, self))
        btn_nav_next = Button(label='❯', width=self.NAV_BUTTON_WIDTH)
        btn_nav_next.on_click(partial(on_click_nav_next, self))
        btn_nav_next_big = Button(label='❯❯', width=self.NAV_BUTTON_WIDTH)
        btn_nav_next_big.on_click(partial(on_click_nav_next, self, 10))
        # layout
        controls = row(
            children=[select_filter])
        nav = row(
            children=[btn_nav_prev_big,
                      btn_nav_prev,
                      btn_nav_action,
                      btn_nav_next,
                      btn_nav_next_big])
        # tabs
        tabs = Tabs(
            id='tabs',
            sizing_mode=self._app.scheme.plot_sizing_mode)
        # model
        model = layout(
            [
                # app settings, top area
                [column(controls, width_policy='min'),
                 Spacer(),
                 column(nav, width_policy='min')],
                Spacer(height=15),
                # layout for tabs
                [tabs]
            ],
            sizing_mode='stretch_width')
        return model, partial(refresh, self)

    def updatemodel(self):
        self.doc.hold()
        self._app.update_figurepage(filter=self._get_filter())
        panels = self._app.generate_model_panels()
        for t in self._app.tabs:
            tab = t(self._app, self._figurepage, self)
            if tab.is_useable():
                panels.append(tab.get_panel())

        # set all tabs (from panels, without None)
        self._get_tabs().tabs = list(filter(None.__ne__, panels))

        # create new data handler
        if self._datahandler is not None:
            self._datahandler.stop()
        self._datahandler = LiveDataHandler(
            doc=self.doc,
            app=self._app,
            figid=self._figid,
            lookback=self.lookback,
            fill_gaps=self.fill_gaps)

        # refresh model
        self._refresh_fnc()
        self.doc.unhold()

    def _get_filter(self):
        res = {}
        if self._filter.startswith('D'):
            res['dataname'] = self._filter[1:]
        elif self._filter.startswith('G'):
            res['group'] = self.plotgroup
        return res

    def _pause(self):
        self._paused = True

    def _resume(self):
        if not self._paused:
            return
        self._datahandler.update()
        self._paused = False

    def _set_data_by_idx(self, idx=None):
        # if a index is provided, ensure that index is within data range
        if idx:
            # don't allow idx to be bigger than max idx
            last_avail_idx = self._app.get_last_idx(self._figid)
            idx = min(idx, last_avail_idx)
            # don't allow idx to be smaller than lookback - 1
            idx = max(idx, self.lookback - 1)
        # create DataFrame based on last index with length of lookback
        df = self._app.generate_data(
            figid=self._figid,
            end=idx,
            back=self.lookback,
            preserveidx=True,
            fill_gaps=self.fill_gaps)
        self._datahandler.set(df)

    def _get_tabs(self):
        return self.model.select_one({'id': 'tabs'})

    def next(self):
        '''
        Request for updating data with rows
        '''
        if not self._paused:
            self._datahandler.update()
        if self._refresh_fnc:
            self._refresh_fnc()

    def stop(self):
        self._datahandler.stop()
        pass
