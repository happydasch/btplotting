from functools import partial

from bokeh.models import Panel, Slider, Button
from bokeh.layouts import column, row

from ..figure import FigureType
from ..tab import BacktraderPlottingTab


class ConfigTab(BacktraderPlottingTab):

    def is_useable(self):
        return (self.client is not None)

    def get_panel(self):

        def on_button_save_config(self):
            # update scheme with new aspectratios
            self.app.p.scheme.obs_aspectratio = slider_obs_aspectratio.value
            self.app.p.scheme.data_aspectratio = slider_data_aspectratio.value
            self.app.p.scheme.vol_aspectratio = slider_vol_aspectratio.value
            self.app.p.scheme.ind_aspectratio = slider_ind_aspectratio.value
            # apply new aspectratios
            for f in self.figurepage.figures:
                ftype = f.get_type()
                if ftype == FigureType.OBS:
                    f.figure.aspect_ratio = slider_obs_aspectratio.value
                elif ftype == FigureType.DATA:
                    f.figure.aspect_ratio = slider_data_aspectratio.value
                elif ftype == FigureType.VOL:
                    f.figure.aspect_ratio = slider_vol_aspectratio.value
                elif ftype == FigureType.IND:
                    f.figure.aspect_ratio = slider_ind_aspectratio.value
                else:
                    raise Exception(f"Unknown type {ftype}")

        slider_obs_aspectratio = Slider(
            title="Observer Aspect Ratio",
            value=self.app.p.scheme.obs_aspectratio,
            start=0.1, end=10.0, step=0.1)
        slider_data_aspectratio = Slider(
            title="Data Aspect Ratio",
            value=self.app.p.scheme.data_aspectratio,
            start=0.1, end=10.0, step=0.1)
        slider_vol_aspectratio = Slider(
            title="Volume Aspect Ratio",
            value=self.app.p.scheme.vol_aspectratio,
            start=0.1, end=10.0, step=0.1)
        slider_ind_aspectratio = Slider(
            title="Indicator Aspect Ratio",
            value=self.app.p.scheme.ind_aspectratio,
            start=0.1, end=10.0, step=0.1)

        button = Button(label="Save", button_type="success", width_policy="min")
        button.on_click(partial(on_button_save_config, self))

        r1 = column(
            [slider_obs_aspectratio,
                slider_data_aspectratio,
                slider_vol_aspectratio,
                slider_ind_aspectratio],
            sizing_mode="scale_width")

        r2 = row(
            [button])

        return Panel(
            child=column(children=[r1, r2], sizing_mode="scale_width"),
            title='Config')
