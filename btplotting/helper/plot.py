
import matplotlib.colors


def convert_color(color):
    '''
    if color is a float value then it is interpreted as a shade of grey
    and converted to the corresponding html color code
    '''
    try:
        val = round(float(color) * 255.0)
        hex_string = '#{0:02x}{0:02x}{0:02x}'.format(val)
        return hex_string
    except ValueError:
        return matplotlib.colors.to_hex(color)


def sanitize_source_name(name: str):
    '''
    removes illegal characters from source name to make it
    compatible with Bokeh
    '''
    forbidden_chars = ' (),.-/*:'
    for fc in forbidden_chars:
        name = name.replace(fc, '_')
    return name
