import backtrader as bt

from .params import get_params_str
from ..utils import get_clock_obj, get_dataname


def obj2label(obj, fullid=False):
    if isinstance(obj, bt.Strategy):
        return strategy2label(obj, fullid)
    elif isinstance(obj, bt.IndicatorBase):
        if not fullid:
            return indicator2label(obj)
        else:
            return f'{indicator2label(obj)}@{indicator2fullid(obj)}'
    elif isinstance(obj, bt.AbstractDataBase):
        if not fullid:
            return get_dataname(obj)
        else:
            return f'{get_dataname(obj)}-{obj.__class__.__name__}'
    elif isinstance(obj, bt.ObserverBase):
        return observer2label(obj)
    elif isinstance(obj, bt.Analyzer):
        return obj.__class__.__name__
    elif isinstance(obj, (bt.LinesOperation,
                          bt.LineSingle,
                          bt.LineIterator,
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


def observer2label(obs):
    return obs.plotlabel()


def indicator2label(ind):
    return ind.plotlabel()


def indicator2fullid(ind):
    '''
    Returns a string listing all involved data feeds. Empty string if
    there is only a single feed in the mix
    '''
    if isinstance(ind, bt.LineActions):
        return 'Line Action'
    names = []
    for x in ind.datas:
        if isinstance(x, bt.AbstractDataBase):
            return obj2label(x)
        elif isinstance(x, bt.LineSeriesStub):
            # indicator target is one specific line of a datafeed
            # add [L] at the end
            return obj2label(get_clock_obj(x)) + ' [L]'
        elif isinstance(x, bt.IndicatorBase):
            names.append(indicator2label(x))
    if len(names) > 0:
        return f'({",".join(names)})'
    return ''
