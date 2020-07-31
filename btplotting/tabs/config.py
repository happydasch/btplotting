from collections import defaultdict
from functools import partial

from bokeh.layouts import column
from bokeh.models import Slider, Button, Paragraph, \
    CheckboxButtonGroup, CheckboxGroup, TextInput

from ..figure import FigureType
from ..tab import BacktraderPlottingTab
from ..utils import get_plotobjs
from ..helper.label import obj2label

import backtrader as bt


class ConfigTab(BacktraderPlottingTab):

    def __init__(self, app, figurepage, client=None):
        super(ConfigTab, self).__init__(app, figurepage, client)
        self.scheme = app.scheme

    def _is_useable(self):
        return (self._client is not None)

    def _on_button_save_config(self):
        # apply config
        self._apply_fill_gaps_config()
        self._apply_lookback_config()
        self._apply_plotgroup_config()
        self._apply_aspectratio_config()
        # update client
        self._client.updatemodel()

    def _create_fill_gaps_config(self):
        title = Paragraph(
            text='Fill Gaps',
            css_classes=['config-title'])

        if self._client.fill_gaps:
            active = [0]
        else:
            active = []
        self.chk_fill_gaps = CheckboxGroup(
            labels=['Fill gaps with data'],
            active=active)

        return column([title, self.chk_fill_gaps], sizing_mode='stretch_width')

    def _apply_fill_gaps_config(self):
        self._client.fill_gaps = (True
                                  if 0 in self.chk_fill_gaps.active
                                  else False)

    def _create_lookback_config(self):
        title = Paragraph(
            text='Lookback period',
            css_classes=['config-title'])
        self.sld_lookback = Slider(
            title='Period for data to plot',
            value=self._client.lookback,
            start=1, end=200, step=1)
        return column([title, self.sld_lookback], sizing_mode='stretch_width')

    def _apply_lookback_config(self):
        self._client.lookback = self.sld_lookback.value

    def _create_plotgroup_config(self):
        self.plotgroup = []
        self.plotgroup_chk = defaultdict(list)
        self.plotgroup_objs = defaultdict(list)
        self.plotgroup_text = None

        def active_obj(obj, selected):
            if not len(selected) or obj.plotinfo.plotid in selected:
                return True
            return False

        title = Paragraph(
            text='Plot Group',
            css_classes=['config-title'])
        options = []

        # get client plot group selection
        if self._client.plotgroup != '':
            selected_plot_objs = self._client.plotgroup.split(',')
        else:
            selected_plot_objs = []

        # get all plot objects
        self.plotgroup_objs = get_plotobjs(
            self._figurepage.strategy,
            order_by_plotmaster=False)

        # create plotgroup checkbox buttons
        for d in self.plotgroup_objs:
            # generate master chk
            master_chk = None
            if not isinstance(d, bt.Strategy):
                active = []
                if active_obj(d, selected_plot_objs):
                    active.append(0)
                    self._add_to_plotgroup(d)
                master_chk = CheckboxButtonGroup(
                    labels=[obj2label(d)], active=active)

            # generate childs chk
            childs_chk = []
            objsd = self.plotgroup_objs[d]
            # sort child objs by type
            objsd.sort(key=lambda x: (FigureType.get_type(x).value))
            # split objs into chunks and store chk
            objsd = [objsd[i:i + 3] for i in range(0, len(objsd), 3)]
            for x in objsd:
                childs = []
                active = []
                for i, o in enumerate(x):
                    childs.append(obj2label(o))
                    if active_obj(o, selected_plot_objs):
                        active.append(i)
                        self._add_to_plotgroup(o)
                # create a chk for every chunk
                if len(childs):
                    chk = CheckboxButtonGroup(
                        labels=childs, active=active)
                    chk.on_change(
                        'active',
                        partial(
                            self._on_update_plotgroups,
                            chk=chk,
                            master=d,
                            childs=x))
                    # if master is not active, disable childs
                    if master_chk and not len(master_chk.active):
                        chk.disabled = True
                    childs_chk.append(chk)
                self.plotgroup_chk[d].append(x)

            # append title for master (this will also include strategy)
            if len(self.plotgroup_objs[d]):
                options.append(Paragraph(text=f'{obj2label(d)}:'))
            # append master_chk and childs_chk to layout
            if master_chk:
                master_chk.on_change(
                    'active',
                    partial(
                        self._on_update_plotgroups,
                        # provide all related chk to master
                        chk=[master_chk] + childs_chk,
                        master=d))
                options.append(master_chk)
            for c in childs_chk:
                options.append(c)

        # text input to display selection
        self.plotgroup_text = TextInput(
            value=','.join(self.plotgroup),
            disabled=True)
        options.append(Paragraph(text='Plot Group Selection:'))
        options.append(self.plotgroup_text)

        return column([title] + options)

    def _add_to_plotgroup(self, obj):
        plotid = obj.plotinfo.plotid
        if plotid not in self.plotgroup:
            self.plotgroup.append(plotid)

    def _remove_from_plotgroup(self, obj):
        plotid = obj.plotinfo.plotid
        if plotid in self.plotgroup:
            self.plotgroup.remove(plotid)

    def _on_update_plotgroups(self, attr, old, new, chk=None, master=None,
                              childs=None):
        '''
        Callback for plot group selection
        '''
        if childs is None:
            # master was clicked
            if not len(new):
                self._remove_from_plotgroup(master)
                # disable all child chk, master has i=0
                for i, c in enumerate(chk[1:]):
                    c.disabled = True
                    for o in self.plotgroup_chk[master][i]:
                        self._remove_from_plotgroup(o)
            else:
                self._add_to_plotgroup(master)
                # enable all childs
                for i, c in enumerate(chk[1:]):
                    c.disabled = False
                    for j in c.active:
                        o = self.plotgroup_chk[master][i][j]
                        self._add_to_plotgroup(o)
        else:
            # child was clicked
            added_diff = [i for i in old + new if i not in old and i in new]
            removed_diff = [i for i in old + new if i in old and i not in new]
            for i in added_diff:
                o = childs[i]
                self._add_to_plotgroup(o)
            for i in removed_diff:
                o = childs[i]
                self._remove_from_plotgroup(o)

        self.plotgroup_text.value = ','.join(self.plotgroup)

    def _apply_plotgroup_config(self):
        # update scheme with new plot group
        self._client.plotgroup = ','.join(self.plotgroup)

    def _create_aspectratio_config(self):
        self.sld_obs_ar = None
        self.sld_data_ar = None
        self.sld_vol_ar = None
        self.sld_ind_ar = None
        title = Paragraph(
            text='Aspect Ratios',
            css_classes=['config-title'])
        self.sld_obs_ar = Slider(
            title='Observer Aspect Ratio',
            value=self.scheme.obs_aspectratio,
            start=0.1, end=20.0, step=0.1)
        self.sld_data_ar = Slider(
            title='Data Aspect Ratio',
            value=self.scheme.data_aspectratio,
            start=0.1, end=20.0, step=0.1)
        self.sld_vol_ar = Slider(
            title='Volume Aspect Ratio',
            value=self.scheme.vol_aspectratio,
            start=0.1, end=20.0, step=0.1)
        self.sld_ind_ar = Slider(
            title='Indicator Aspect Ratio',
            value=self.scheme.ind_aspectratio,
            start=0.1, end=20.0, step=0.1)
        return column([title,
                       self.sld_obs_ar,
                       self.sld_data_ar,
                       self.sld_vol_ar,
                       self.sld_ind_ar])

    def _apply_aspectratio_config(self):
        # update scheme with new aspect ratios
        self.scheme.obs_aspectratio = self.sld_obs_ar.value
        self.scheme.data_aspectratio = self.sld_data_ar.value
        self.scheme.vol_aspectratio = self.sld_vol_ar.value
        self.scheme.ind_aspectratio = self.sld_ind_ar.value

    def _get_panel(self):
        '''
        Returns the panel for tab
        '''
        title = Paragraph(
            text='Client Configuration',
            css_classes=['panel-title'])
        button = Button(
            label='Save',
            button_type='success',
            width_policy='min')
        button.on_click(self._on_button_save_config)
        # layout for config area
        config = column(
            [self._create_fill_gaps_config(),
             self._create_lookback_config(),
             self._create_plotgroup_config(),
             self._create_aspectratio_config()],
            sizing_mode='scale_width')
        # layout for config buttons
        buttons = column([button])
        # config layout
        child = column(
            children=[title, config, buttons],
            sizing_mode='scale_width')

        return child, 'Config'
