#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='btplotting',

    version='0.1.0',

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
        'bokeh~=2.1.1',
        'jinja2',
        'pandas',
        'matplotlib',
    ],
)
