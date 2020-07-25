import numpy as np


def cds_op_gt(a, b):
    '''
    Operator for gt
    will create a new column with values
    from b if a > b else a
    '''
    res = np.where(a > b, b, a)
    return res


def cds_op_lt(a, b):
    '''
    Operator for lt
    will create a new column with values
    from b if a < b else a
    '''
    res = np.where(a < b, b, a)
    return res


def cds_op_non(a, b):
    '''
    Operator for non
    will return b as new column
    '''
    return b


def cds_op_color(a, b, color_up, color_down):
    '''
    Operator for color generation
    will return a column with colors
    To provide color values, use functools.partial.
    Example:
    partial(cds_op_color, color_up=color_up, color_down=color_down)
    '''
    c_up = np.full(len(a), color_up)
    c_down = np.full(len(a), color_down)
    res = np.where(b >= a, c_up, c_down)
    return res
