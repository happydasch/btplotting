import setuptools
from distutils.util import convert_path

with open("README.md", "r") as fh:
    long_description = fh.read()

main_ns = {}
ver_path = convert_path('btplotting/version.py')
with open(ver_path) as ver_file:
    exec(ver_file.read(), main_ns)

setuptools.setup(
    name='btplotting',
    version=main_ns['__version__'],
    description='Plotting package for Backtrader (Bokeh)',
    python_requires='>=3.6',
    author='happydasch',
    author_email='daniel@vcard24.de',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='GPLv3+',
    url="https://github.com/happydasch/btplotting",
    project_urls={
        "Bug Tracker": "https://github.com/happydasch/btplotting/issues",
        "Documentation": "https://github.com/happydasch/btplotting/wiki",
        "Source Code": "https://github.com/happydasch/btplotting",
        "Demos": "https://github.com/happydasch/btplotting/tree/gh-pages",
    },

    # What does your project relate to?
    keywords=['trading', 'development', 'plotting', 'backtrader'],

    packages=setuptools.find_packages(),
    package_data={'btplotting': ['templates/*.j2', 'templates/js/*.js']},

    install_requires=[
        'backtrader',
        'bokeh',
        'jinja2',
        'pandas',
        'matplotlib',
    ],
)
