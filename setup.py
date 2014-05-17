#!/usr/bin/env python
# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import sys
import os

try:
    from setuptools import setup
    using_setuptools = True
except ImportError:
    from distutils.core import setup
    using_setuptools = False

setup(
    name = "conda",
    version="0.1",
    cmdclass=versioneer.get_cmdclass(),
    author = "Continuum Analytics, Inc.",
    author_email = "ijstokes@continuum.io",
    url = "https://github.com/conda/conda-launch",
    license = "BSD",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
    ],
    description = "appify ipython notebooks",
    long_description = open('README.md').read(),
    packages = ['ipyapp'],
    install_requires = ['flask', 'requests'],
    entry_points = {
        'console_scripts':
            ['conda-launch = ipyapp.cli:main']
    }
)
