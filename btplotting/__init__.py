import sys
from .app import BacktraderPlotting  # noqa: F401
from .analyzers import LivePlotAnalyzer as BacktraderPlottingLive  # noqa: F401
from .optbrowser import OptBrowser as BacktraderPlottingOptBrowser  # noqa: F401, E501

# initialize analyzer tables
from .analyzer_tables import inject_datatables
inject_datatables()

if 'ipykernel' in sys.modules:
    from bokeh.io import output_notebook
    output_notebook()
