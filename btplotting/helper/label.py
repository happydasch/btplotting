import backtrader as bt

from .params import get_params_str
from ..utils import get_clock_obj, get_dataname


def obj2label(obj, fullid=False):
    if isinstance(obj, bt.Strategy):
        return strategy2label(obj, fullid)
    elif isinstance(obj, bt.IndicatorBase):
        return indicator2label(obj, fullid)
    elif isinstance(obj, bt.AbstractDataBase):
        return data2label(obj, fullid)
    elif isinstance(obj, bt.ObserverBase):
        return observer2label(obj, fullid)
    elif isinstance(obj, bt.Analyzer):
        return obj.__class__.__name__
    elif isinstance(obj, bt.MultiCoupler):
        return obj2label(obj.datas[0], fullid)
    elif isinstance(obj, (bt.LinesOperation,
                          bt.LineSingle,
                          bt.LineSeriesStub)):
        return obj.__class__.__name__
    else:
        raise RuntimeError(f'Unsupported type: {obj.__class__}')


def strategy2label(strategy, params=False):
    label = strategy.__class__.__name__
    if params:
        param_labels = get_params_str(strategy.params)
        if len(param_labels) > 0:
            label += f' [{param_labels}]'
    return label


def data2label(data, fullid=False):
    if fullid:
        return f'{get_dataname(data)}-{data.__class__.__name__}'
    else:
        return get_dataname(data)


def observer2label(obs, fullid=False):
    if fullid:
        return obs.plotlabel()
    else:
        return obs.plotinfo.plotname or obs.__class__.__name__


def indicator2label(ind, fullid=False):
    if fullid:
        return ind.plotlabel()
    else:
        return ind.plotinfo.plotname or ind.__class__.__name__


def obj2data(obj):
    '''
    Returns a string listing all involved data feeds. Empty string if
    there is only a single feed in the mix
    '''
    if isinstance(obj, bt.LineActions):
        return 'Line Action'
    elif isinstance(obj, bt.AbstractDataBase):
        return obj2label(obj)
    elif isinstance(obj, bt.IndicatorBase):
        names = []
        for x in obj.datas:
            if isinstance(x, bt.AbstractDataBase):
                return obj2label(x)
            elif isinstance(x, bt.IndicatorBase):
                names.append(indicator2label(x, False))
            elif isinstance(x, bt.LineSeriesStub):
                # indicator target is one specific line of a datafeed
                # add [L] at the end
                return obj2label(get_clock_obj(x)) + ' [L]'
        if len(names) > 0:
            return ",".join(names)
    else:
        raise RuntimeError(f'Unsupported type: {obj.__class__}')
    return ''
