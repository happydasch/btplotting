from bokeh.layouts import column, row
from bokeh.models import Slider, Button, Paragraph

from ..figure import FigureType
from ..tab import BacktraderPlottingTab


class ConfigTab(BacktraderPlottingTab):
    '''
    def _test(self, figid=0):
        fp = self.get_figurepage(figid)
        strategy = fp.strategy
        from libs.btplotting.utils import get_dataname, get_clock_obj
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
    '''
    def __init__(self, app, figurepage, client=None):
        super(ConfigTab, self).__init__(app, figurepage, client)
        self.content = None
        self.sld_obs_ar = None
        self.sld_data_ar = None
        self.sld_vol_ar = None
        self.sld_ind_ar = None
        self.scheme = app.p.scheme

    def _is_useable(self):
        return (self._client is not None)

    def _on_button_save_config(self):
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

        button = Button(
            label='Save',
            button_type='success',
            width_policy='min')
        button.on_click(self._on_button_save_config)

        title = Paragraph(
            text='Client Configuration',
            css_classes=['panel-title'])
        r1 = column(
            [self.sld_obs_ar,
             self.sld_data_ar,
             self.sld_vol_ar,
             self.sld_ind_ar],
            sizing_mode='scale_width')
        r2 = row(
            [button])
        child = column(
            children=[title, r1, r2],
            sizing_mode='scale_width')

        return child, 'Config'
