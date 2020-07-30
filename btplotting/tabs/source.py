import inspect

from bokeh.models import PreText, Paragraph
from bokeh.layouts import column

from ..tab import BacktraderPlottingTab


class SourceTab(BacktraderPlottingTab):

    def _is_useable(self):
        return not self._app.is_iplot()

    def _get_panel(self):
        title = Paragraph(
            text='Source Code',
            css_classes=['panel-title'])
        child = column(
            [title,
             PreText(text=inspect.getsource(
                 self._figurepage.strategy.__class__))],
            sizing_mode='scale_both')
        return child, 'Source Code'
