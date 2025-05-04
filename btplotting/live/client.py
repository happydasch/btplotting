import time
import logging
from functools import partial
from threading import Thread

from bokeh.layouts import column, row, layout
from bokeh.models import Select, Spacer, Tabs, Button, Slider
from bokeh.document import without_document_lock

from .datahandler import LiveDataHandler
from ..tabs import ConfigTab
from ..utils import get_datanames

_logger = logging.getLogger(__name__)


class LiveClient:
    '''
    LiveClient provides live plotting functionality.
    '''

    NAV_BUTTON_WIDTH = 35

    def __init__(self, doc, app, strategy, lookback, paused_at_beginning, interval=0.01):
        self._app = app
        self._doc = doc
        self._strategy = strategy
        self._interval = interval
        self._thread = Thread(target=self._t_thread, daemon=True)
        self._refresh_fnc = None
        self._datahandler = None
        self._figurepage = None
        self._running = True
        self._paused = paused_at_beginning
        self._lastlen = -1
        self._filterdata = ''
        # plotgroup for filter
        self.plotgroup = ''
        # amount of candles to plot
        self.lookback = lookback
        # model is the root model for bokeh and will be set in baseapp
        self.model = None

        # append config tab if default tabs should be added
        if self._app.p.use_default_tabs:
            self._app.tabs.append(ConfigTab)
        # set plotgroup from app params if provided
        if self._app.p.filterdata and self._app.p.filterdata['group']:
            self.plotgroup = self._app.p.filterdata['group']
        # create figurepage
        self._figid, self._figurepage = self._app.create_figurepage(
            self._strategy, filldata=False)

        # create model and finish initialization
        self.model, self._refresh_fnc = self._createmodel()
        self.refreshmodel()
        self._thread.start()

    def _t_thread(self):
        '''
        Thread method for updates
        '''
        if self._interval == 0:
            return
        while self._running:
            if not self.is_paused():
                if len(self._strategy) == self._lastlen:
                    continue
                self._lastlen = len(self._strategy)
                if self._doc.session_context:
                    self._doc.add_next_tick_callback(self.safe_update)
            time.sleep(self._interval)

    def rate_limited(max_per_second):
        min_interval = 1.0 / float(max_per_second)
        def decorate(func):
            last_time_called = [0.0]
            @wraps(func)
            def rate_limited_function(*args, **kwargs):
                elapsed = time.time() - last_time_called[0]
                left_to_wait = min_interval - elapsed
                if left_to_wait > 0:
                    time.sleep(left_to_wait)
                ret = func(*args, **kwargs)
                last_time_called[0] = time.time()
                return ret
            return rate_limited_function
        return decorate


    @without_document_lock
    def safe_update(self):
        try:
            # Instead of directly updating, schedule the update for the next tick
            self._doc.add_next_tick_callback(self._perform_update)
        except Exception as e:
            _logger.error(f"Error during safe_update: {e}")

    def _perform_update(self):
        try:
            self._datahandler.update()
            self.refresh()
        except Exception as e:
            _logger.error(f"Error during _perform_update: {e}")

    def _createmodel(self):

        def on_select_filterdata(self, a, old, new):
            _logger.debug(f'Switching filterdata to {new}...')
            self._datahandler.stop()
            self._filterdata = new
            self.refreshmodel()
            _logger.debug('Switching filterdata finished')

        def on_click_nav_action(self):
            if not self._paused:
                self._pause()
            else:
                self._resume()
            self._doc.add_next_tick_callback(partial(update_nav_buttons, self))

        def on_click_nav_prev(self, steps=1):
            self._pause()
            self._doc.add_next_tick_callback(partial(self._set_data_by_idx, self._datahandler.get_last_idx() - steps))
            self._doc.add_next_tick_callback(partial(update_nav_buttons, self))

        def on_click_nav_next(self, steps=1):
            self._pause()
            self._doc.add_next_tick_callback(partial(self._set_data_by_idx, self._datahandler.get_last_idx() + steps))
            self._doc.add_next_tick_callback(partial(update_nav_buttons, self))

        def refresh(self, now=False):
            if now:
                update_nav_buttons(self)
            else:
                self._doc.add_next_tick_callback(partial(update_nav_buttons, self))

        def reset_nav_buttons(self):
            btn_nav_prev.disabled = True
            btn_nav_prev_big.disabled = True
            btn_nav_next.disabled = True
            btn_nav_next_big.disabled = True
            btn_nav_action.label = '❙❙'

        def update_nav_buttons(self):
            try:
                last_idx = self._datahandler.get_last_idx()
                last_avail_idx = self._app.get_last_idx(self._figid)

                if self._paused:
                    btn_nav_action.label = '▶'
                else:
                    btn_nav_action.label = '❙❙'

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
            except Exception as e:
                _logger.error(f"Error during update_nav_buttons: {e}")

        # filter selection
        datanames = get_datanames(self._strategy)
        options = [('', 'Strategy')]
        for d in datanames:
            options.append(('D' + d, f'Data: {d}'))
        options.append(('G', 'Plot Group'))
        self._filterdata = 'D' + datanames[0]
        select_filterdata = Select(
            value=self._filterdata,
            options=options)
        select_filterdata.on_change(
            'value',
            partial(on_select_filterdata, self))

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
            children=[select_filterdata])
        nav = row(
            children=[btn_nav_prev_big,
                      btn_nav_prev,
                      btn_nav_action,
                      btn_nav_next,
                      btn_nav_next_big])
        slider = Slider(
            title='Period for data to plot',
            value=self.lookback,
            start=1, end=200, step=1)

        # tabs
        tabs = Tabs(
            sizing_mode='stretch_width')

        # model
        model = layout(
            [
                # app settings, top area
                [column(controls, width_policy='min'),
                 column(slider, sizing_mode='stretch_width'),
                 column(nav, width_policy='min')],
                Spacer(height=15),
                # layout for tabs
                [tabs]
            ],
            sizing_mode='stretch_width')

        # return model and a refresh function
        return model, partial(refresh, self)

    def _get_filterdata(self):
        res = {}
        if self._filterdata.startswith('D'):
            res['dataname'] = self._filterdata[1:]
        elif self._filterdata.startswith('G'):
            res['group'] = self.plotgroup
        return res

    def _get_tabs(self):
        return self.model.select_one({'type': Tabs})

    def _set_data_by_idx(self, idx=None):
        try:
            if idx:
                idx = max(idx, self.lookback - 1)
                last_avail_idx = self._app.get_last_idx(self._figid)
                idx = min(idx, last_avail_idx)

            clk = self._figurepage.data_clock._get_clk()
            end = self._figurepage.data_clock.get_dt_at_idx(clk, idx)
            df = self._app.get_data(
                end=end,
                figid=self._figid,
                back=self.lookback)
            self._datahandler.set_df(df)
        except Exception as e:
            _logger.error(f"Error during _set_data_by_idx: {e}")

    def _pause(self):
        self._paused = True

    def _resume(self):
        if not self._paused:
            return
        self._paused = False

    def get_app(self):
        return self._app

    def get_doc(self):
        return self._doc

    def get_figurepage(self):
        return self._figurepage

    def get_figid(self):
        return self._figid

    def is_paused(self):
        return self._paused

    def refresh(self):
        try:
            if self._refresh_fnc:
                self._refresh_fnc(False)
        except Exception as e:
            _logger.error(f"Error during refresh: {e}")

    def refreshmodel(self):
        try:
            if self._datahandler is not None:
                self._datahandler.stop()
            self._app.update_figurepage(filterdata=self._get_filterdata())
            self._datahandler = LiveDataHandler(self)
            tab_panels = self._app.generate_bokeh_model_tab_panels()
            for t in self._app.tabs:
                tab = t(self._app, self._figurepage, self)
                if tab.is_useable():
                    tab_panels.append(tab.get_tab_panel())
            self._get_tabs().tabs = list(filter(None.__ne__, tab_panels))
            self.refresh()
        except Exception as e:
            _logger.error(f"Error during refreshmodel: {e}")

    def next(self):
        try:
            if self._interval != 0:
                return
            if len(self._strategy) == self._lastlen:
                return
            self._lastlen = len(self._strategy)
            self._datahandler.update()
        except Exception as e:
            _logger.error(f"Error during next: {e}")

    def stop(self):
        try:
            self._running = False
            self._thread.join()
            self._datahandler.stop()
        except Exception as e:
            _logger.error(f"Error during stop: {e}")
