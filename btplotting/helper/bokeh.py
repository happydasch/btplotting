from jinja2 import Environment, PackageLoader


def generate_stylesheet(scheme, template='basic.css.j2'):
    '''
    Generates stylesheet with values from scheme
    '''
    env = Environment(loader=PackageLoader('btplotting', 'templates'))
    templ = env.get_template(template)

    css = templ.render(scheme.__dict__)
    return css
