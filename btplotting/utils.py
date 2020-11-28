import itertools
from collections import defaultdict

import backtrader as bt


def get_plotobjs(strategy, include_non_plotable=False,
                 order_by_plotmaster=False):
    '''
    Returns all plotable objects of a strategy

    By default the result will be ordered by the
    data the object is aligned to. If order_by_plotmaster
    is True, objects will be aligned to their plotmaster.
    '''
    datas = strategy.datas
    inds = strategy.getindicators()
    obs = strategy.getobservers()
    objs = defaultdict(list)
    # ensure strategy is included
    objs[strategy] = []
    # first loop through datas
    for d in datas:
        if not include_non_plotable and not d.plotinfo.plot:
            continue
        objs[d] = []
    # next loop through all ind and obs and set them to
    # the corresponding data clock
    for obj in itertools.chain(inds, obs):
        # check for base classes
        if not isinstance(obj, (bt.IndicatorBase,
                                bt.MultiCoupler,
                                bt.ObserverBase)):
            continue
        # check for plotinfos
        if not hasattr(obj, 'plotinfo'):
            # no plotting support cause no plotinfo attribute
            # available - so far LineSingle derived classes
            continue
        # should this indicator be plotted?
        if (not include_non_plotable
                and (not obj.plotinfo.plot or obj.plotinfo.plotskip)):
            continue
        # append object to the data object
        pltmaster = get_plotmaster(obj)
        data = get_clock_obj(obj, True)
        if pltmaster in objs:
            objs[pltmaster].append(obj)
        elif data in objs:
            objs[data].append(obj)

    if not order_by_plotmaster:
        return objs

    # order objects by its plotmaster
    pobjs = defaultdict(list)
    for d in objs:
        pmaster = get_plotmaster(d)
        # add all datas, if a data has a plotmaster, add it to plotmaster
        if pmaster is d and pmaster not in pobjs:
            pobjs[pmaster] = []
        elif pmaster is not None and pmaster is not d:
            pobjs[pmaster].append(d)

        for o in objs[d]:
            pmaster = get_plotmaster(o.plotinfo.plotmaster)
            subplot = o.plotinfo.subplot
            if subplot and pmaster is None:
                pobjs[o] = []
            elif pmaster is not None:
                pobjs[pmaster].append(o)
            else:
                pmaster = get_plotmaster(get_clock_obj(o, True))
                if pmaster is not None and pmaster in pobjs:
                    pobjs[pmaster].append(o)
    # return objects ordered by plotmaster
    return pobjs


def get_plotmaster(obj):
    '''
    Resolves the plotmaster of the given object
    '''
    if obj is None:
        return None

    while True:
        pm = obj.plotinfo.plotmaster
        if pm is None:
            break
        else:
            obj = pm
    if isinstance(obj, bt.Strategy):
        return None
    return obj


def get_last_avail_idx(strategy, dataname=False):
    '''
    Returns the last available index of a data source
    '''
    if dataname is not False:
        data = strategy.getdatabyname(dataname)
    else:
        data = strategy
    offset = 0
    while True:
        if (len(data) > offset
                and data.datetime[-offset] != data.datetime[-offset]):
            offset += 1
            continue
        break
    return len(data) - 1 - offset


def filter_obj(obj, filter):
    '''
    Returns if the given object should be filtered.
    False if object should not be filtered out, 
    True if object should be filtered out.
    '''

    if filter is None:
        return False

    dataname = get_dataname(obj)
    plotid = obj.plotinfo.plotid

    # filter by dataname
    if 'dataname' in filter:
        if dataname is not False:
            if isinstance(filter['dataname'], str):
                if dataname != filter['dataname']:
                    return True
            elif isinstance(filter['dataname', list]):
                if dataname not in filter['dataname']:
                    return True
    if 'group' in filter:
        if isinstance(filter['group'], str):
            if filter['group'] != '':
                plotids = filter['group'].split(',')
                if plotid not in plotids:
                    return True

    return False


def get_datanames(strategy, filter=True):
    '''
    Returns the names of all data sources
    '''
    datanames = []
    for d in strategy.datas:
        if not filter or d.plotinfo.plot is not False:
            datanames.append(get_dataname(d))
    return datanames


def get_dataname(obj):
    '''
    Returns the name of the data for the given object
    If the data for a object is a strategy then False will
    be returned.
    '''
    data = get_clock_obj(obj, True)
    if isinstance(data, bt.Strategy):
        # strategy will have no dataname
        return False
    elif isinstance(data, bt.AbstractDataBase):
        # data feeds are end points
        # try some popular attributes that might carry a name
        # _name: user assigned value upon instantiation
        # _dataname: underlying bt dataname (is always available)
        # if that fails, use str
        for n in ['_name', '_dataname']:
            val = getattr(data, n)
            if val is not None:
                break
        if val is None:
            val = str(data)
        return val
    else:
        raise Exception(
            f'Unsupported data: {obj.__class__}')


def get_smallest_dataname(strategy, datanames):
    '''
    Returns the smallest dataname from a list of
    datanames
    '''
    data = False
    for d in datanames:
        if not d:
            continue
        tmp = strategy.getdatabyname(d)
        if (data is False
            or (tmp._timeframe < data._timeframe)
            or (tmp._timeframe == data._timeframe
                and tmp._compression < data._compression)):
            data = tmp
    if data is False:
        return data
    return get_dataname(data)


def get_clock_obj(obj, resolve_to_data=False):
    '''
    Returns a clock object to use for building data
    A clock object can be either a strategy, data source,
    indicator or a observer.
    '''
    if isinstance(obj, bt.LinesOperation):
        # indicators can be created to run on a line
        # (instead of e.g. a data object) in that case grab
        # the owner of that line to find the corresponding clock
        # also check for line actions like "macd > data[0]"
        return get_clock_obj(obj._clock, resolve_to_data)
    elif isinstance(obj, (bt.LineSingle)):
        # if we have a line, return its owners clock
        return get_clock_obj(obj._owner, resolve_to_data)
    elif isinstance(obj, bt.LineSeriesStub):
        # if its a LineSeriesStub object, take the first line
        # and get the clock from it
        return get_clock_obj(obj.lines[0], resolve_to_data)
    elif isinstance(obj, (bt.IndicatorBase, bt.MultiCoupler, bt.ObserverBase)):
        # a indicator and observer can be a clock, internally
        # it is obj._clock
        if resolve_to_data:
            return get_clock_obj(obj._clock, resolve_to_data)
        clk = obj
    elif isinstance(obj, bt.StrategyBase):
        # a strategy can be a clock, internally it is obj.data
        clk = obj
    elif isinstance(obj, bt.AbstractDataBase):
        clk = obj
    else:
        raise Exception(
            f'Unsupported clock: {obj.__class__}')
    return clk


def get_clock_line(obj):
    '''
    Find the corresponding clock for an object.
    A clock is a datetime line that holds timestamps
    for the line in question.
    '''
    clk = get_clock_obj(obj)
    return clk.lines.datetime


def get_source_id(source):
    '''
    Returns a unique source id for given source.
    This is used for unique column names.
    '''
    return str(id(source))
