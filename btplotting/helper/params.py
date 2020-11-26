import backtrader as bt


def paramval2str(name, value):
    if value is None:  # catch None value early here!
        return str(value)
    elif name == "timeframe":
        return bt.TimeFrame.getname(value, 1)
    elif isinstance(value, float):
        return f"{value:.2f}"
    elif isinstance(value, (list, tuple)):
        vals = []
        for v in value:
            if isinstance(v, (list, tuple)):
                v = f'[{paramval2str(name, v)}]'
            vals.append(str(v))
        return ','.join(vals)
    elif isinstance(value, type):
        return value.__name__
    else:
        return str(value)


def get_nondefault_params(params: object):
    return {key: params._get(key)
            for key in params._getkeys()
            if not params.isdefault(key)}


def get_params(params):
    return {key: params._get(key) for key in params._getkeys()}


def get_params_str(params):
    user_params = get_nondefault_params(params)
    plabs = [f'{x}: {paramval2str(x, y)}' for x, y in user_params.items()]
    plabs = '/'.join(plabs)
    return plabs
