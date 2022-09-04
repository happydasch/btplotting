from jinja2 import Environment, PackageLoader


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
