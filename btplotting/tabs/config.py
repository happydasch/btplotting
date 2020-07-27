from bokeh.layouts import column
from bokeh.models import Slider, Button, Paragraph, CheckboxGroup, \
    CheckboxButtonGroup, Spacer

from ..figure import FigureType
from ..tab import BacktraderPlottingTab
from ..utils import get_plot_objs
from ..helper.label import obj2label

import backtrader as bt


class ConfigTab(BacktraderPlottingTab):

    def __init__(self, app, figurepage, client=None):
        super(ConfigTab, self).__init__(app, figurepage, client)
        self.sld_obs_ar = None
        self.sld_data_ar = None
        self.sld_vol_ar = None
        self.sld_ind_ar = None
        self.scheme = app.p.scheme

    def _is_useable(self):
        return (self._client is not None)

    def _on_button_save_config(self):
        self._apply_strategy_plot_config()
        self._apply_aspectratio_config()

    def _create_strategy_plot_config(self):
        title = Paragraph(
            text='Strategy Plot Selection',
            css_classes=['config-title'])
        options = []

        objs = get_plot_objs(
            self._figurepage.strategy,
            order_by_plotmaster=True)
        print('-' * 50)
        for d in objs:
            if not isinstance(d, bt.Strategy):
                options.append(CheckboxButtonGroup(
                    labels=[obj2label(d)], active=[0]))
            childs = []
            active = []
            for i, o in enumerate(objs[d]):
                childs.append(obj2label(o))
                active.append(i)
            if len(childs):
                options.append(CheckboxButtonGroup(
                    labels=childs, active=active))
            options.append(Spacer(height=20))

        return column([title] + options)

    def _apply_strategy_plot_config(self):
        pass

    def _create_aspectratio_config(self):
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
        # apply new aspect ratios
        for f in self._figurepage.figures:
            ftype = f.get_type()
            if ftype == FigureType.OBS:
                f.figure.aspect_ratio = self.sld_obs_ar.value
            elif ftype == FigureType.DATA:
                f.figure.aspect_ratio = self.sld_data_ar.value
            elif ftype == FigureType.VOL:
                f.figure.aspect_ratio = self.sld_vol_ar.value
            elif ftype == FigureType.IND:
                f.figure.aspect_ratio = self.sld_ind_ar.value
            else:
                raise Exception(f'Unknown type {ftype}')

    def _get_panel(self):
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
            [self._create_strategy_plot_config(),
             self._create_aspectratio_config()],
            sizing_mode='scale_width')
        # layout for config buttons
        buttons = column([button])
        # config layout
        child = column(
            children=[title, config, buttons],
            sizing_mode='scale_width')

        return child, 'Config'
