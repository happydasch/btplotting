import logging
from functools import partial

from bokeh.io import curdoc
from bokeh.layouts import column, row, layout
from bokeh.models import Select, Spacer, Tabs, Button

from .datahandler import LiveDataHandler
from ..tabs import ConfigTab
from ..utils import get_last_idx, list_datadomains

_logger = logging.getLogger(__name__)


class LiveClient:

    '''
    LiveClient provides live plotting functionality.
    '''

    NAV_BUTTON_WIDTH = 38

    def __init__(self, doc, app, strategy, lookback):
        self._update_fnc = None
        self._datahandler = None
        self._lookback = lookback
        self._paused = False
        self.doc = doc
        self.app = app
        self.strategy = strategy
        self.figureid = None
        self.figurepage = None
        self.datadomain = False
        self.model = None

        # append config tab
        self.app.tabs.append(ConfigTab)
        # create model
        self.model, self._update_fnc = self._createmodel()
        # create figurepage
        self.figureid, self.figurepage = self.app.create_figurepage(
            self.strategy, filldata=False)
        # update model with current figurepage
        self._updatemodel()

    def _createmodel(self):

        def on_select_datadomain(self, a, old, new):
            _logger.debug(f"Switching datadomain {new}...")
            self.datadomain = new
            doc = curdoc()
            doc.hold()
            self._updatemodel()
            doc.unhold()
            _logger.debug(f"Switching datadomain finished")

        def on_click_nav_action(self):
            if not self._paused:
                self._pause()
            else:
                self._resume()
            update(self)

        def on_click_nav_prev(self, steps=1):
            self._pause()
            self._set_data_by_idx(self._datahandler.get_last_idx() - steps)
            update_nav_buttons(self)

        def on_click_nav_next(self, steps=1):
            self._pause()
            self._set_data_by_idx(self._datahandler.get_last_idx() + steps)
            update_nav_buttons(self)

        def update(self):
            self.doc.add_next_tick_callback(partial(update_nav_buttons, self))

        def reset_nav_buttons(self):
            btn_nav_prev.disabled = True
            btn_nav_next.disabled = True
            btn_nav_action.label = "‖"

        def update_nav_buttons(self):
            last_idx = self._datahandler.get_last_idx()
            last_avail_idx = get_last_idx(self.strategy, self.datadomain)

            if last_idx < self._lookback:
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
                btn_nav_action.label = "▶"
            else:
                btn_nav_action.label = "❙❙"

        # datadomain selection
        datadomains = list_datadomains(self.strategy)
        self.datadomain = datadomains[0]
        select_datadomain = Select(
            value=self.datadomain,
            options=datadomains)
        select_datadomain.on_change(
            'value',
            partial(on_select_datadomain, self))
        # nav
        btn_nav_prev = Button(label="❮", width=self.NAV_BUTTON_WIDTH)
        btn_nav_prev.on_click(partial(on_click_nav_prev, self))
        btn_nav_prev_big = Button(label="❮❮", width=self.NAV_BUTTON_WIDTH)
        btn_nav_prev_big.on_click(partial(on_click_nav_prev, self, 10))
        btn_nav_action = Button(label="❙❙", width=self.NAV_BUTTON_WIDTH)
        btn_nav_action.on_click(partial(on_click_nav_action, self))
        btn_nav_next = Button(label="❯", width=self.NAV_BUTTON_WIDTH)
        btn_nav_next.on_click(partial(on_click_nav_next, self))
        btn_nav_next_big = Button(label="❯❯", width=self.NAV_BUTTON_WIDTH)
        btn_nav_next_big.on_click(partial(on_click_nav_next, self, 10))
        # layout
        controls = row(
            children=[select_datadomain])
        nav = row(
            children=[btn_nav_prev_big,
                      btn_nav_prev,
                      btn_nav_action,
                      btn_nav_next,
                      btn_nav_next_big])
        # tabs
        tabs = Tabs(id="tabs", sizing_mode=self.app.p.scheme.plot_sizing_mode)
        # model
        model = layout(
            [
                # app settings, top area
                [column(controls, width_policy="min"),
                 Spacer(),
                 column(nav, width_policy="min")],
                Spacer(height=15),
                # layout for tabs
                [tabs]
            ],
            sizing_mode="stretch_width")
        return model, partial(update, self)

    def _updatemodel(self):
        self.app.update_figurepage(self.figureid, self.datadomain)
        panels = self.app.generate_model_panels(self.figurepage)
        for t in self.app.tabs:
            tab = t(self.app, self.figurepage, self)
            if tab.is_useable():
                panels.append(tab.get_panel())

        # set all tabs (from panels, without None)
        self._get_tabs().tabs = list(filter(None.__ne__, panels))

        # create new data handler
        self._datahandler = LiveDataHandler(
            self,
            self._lookback,
            self.datadomain)

        # notify model about change
        self._update_fnc()

    def _pause(self):
        self._paused = True

    def _resume(self):
        if not self._paused:
            return
        self._set_data_by_idx()
        self._paused = False

    def _set_data_by_idx(self, idx=None):
        # if a index is provided, ensure that index is within data range
        if idx:
            # don't allow idx to be bigger than max idx
            last_avail_idx = get_last_idx(self.strategy, self.datadomain)
            idx = min(idx, last_avail_idx)
            # don't allow idx to be smaller than lookback - 1
            idx = max(idx, self._lookback - 1)
        # create DataFrame based on last index with length of lookback
        df = self.app.build_data(
            strategy=self.strategy,
            datadomain=self.datadomain,
            end=idx,
            back=self._lookback,
            preserveidx=True)
        self._datahandler.set(df)

    def _get_tabs(self):
        return self.model.select_one({"id": "tabs"})

    def update(self, rows):
        '''
        Request for updating data with rows
        '''

        if not self._paused and self._datahandler:
            self._datahandler.update(rows)
        if self._update_fnc:
            self._update_fnc()
