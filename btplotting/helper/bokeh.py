from jinja2 import Environment, PackageLoader

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


def generate_stylesheet(scheme, template='basic.css.j2'):
    '''
    Generates stylesheet with values from scheme
    '''
    env = Environment(loader=PackageLoader('btplotting', 'templates'))
    templ = env.get_template(template)

    css = templ.render(dict(
        datatable_row_color_even=scheme.table_color_even,
        datatable_row_color_odd=scheme.table_color_odd,
        datatable_header_color=scheme.table_header_color,
        tab_active_background_color=scheme.tab_active_background_color,
        tab_active_color=scheme.tab_active_color,

        tooltip_background_color=scheme.tooltip_background_color,
        tooltip_text_color_label=scheme.tooltip_text_label_color,
        tooltip_text_color_value=scheme.tooltip_text_value_color,
        body_background_color=scheme.body_background_color,
        tag_pre_background_color=scheme.tag_pre_background_color,
        tag_pre_text_color=scheme.tag_pre_text_color,
        headline_color=scheme.plot_title_text_color,
        text_color=scheme.text_color))
    return css
