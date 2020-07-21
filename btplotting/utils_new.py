import backtrader as bt


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
        if data.datetime[-offset] != data.datetime[-offset]:
            offset += 1
            continue
        break
    return len(data) - 1 - offset


def get_datanames(strategy):
    '''
    Returns the names of all data sources
    '''
    datanames = []
    for d in strategy.datas:
        datanames.append(get_dataname(d))
    return datanames


def get_dataname(obj):
    '''
    Returns the name of the data for the given object
    If the data for a object is a strategy then False will
    be returned.
    '''
    data = get_data_obj(obj)
    if isinstance(data, bt.Strategy):
        # strategy will have no datadomain
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


def get_data_obj(obj):
    '''
    Returns the data object of the given object
    This will be either a data source or a strategy
    '''
    if isinstance(obj, (bt.Strategy, bt.AbstractDataBase)):
        # strategies and data feeds are end points
        return obj
    elif isinstance(obj, (bt.IndicatorBase, bt.ObserverBase)):
        # to get the data obj for ind and obs, use clock
        return get_data_obj(obj._clock)
    else:
        # try to find a clock as last ressort
        return get_data_obj(get_clock_obj(obj))


def get_clock_obj(obj):
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
        return get_clock_obj(obj._clock)
    elif isinstance(obj, bt.LineSingle):
        # if we have a line, return its owners clock
        return get_clock_obj(obj._owner)
    elif isinstance(obj, bt.LineSeriesStub):
        # if its a LineSeriesStub object, take the first line
        # and get the clock from it
        return get_clock_obj(obj.lines[0])
    elif isinstance(obj, bt.StrategyBase):
        # a strategy can be a clock, internally it is obj.data
        clk = obj
    elif isinstance(obj, (bt.IndicatorBase, bt.ObserverBase)):
        # a indicator and observer can be a clock, internally
        # it is obj._clock
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
