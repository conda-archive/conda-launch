#!/usr/bin/env python
# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

import versioneer

versioneer.versionfile_source = 'ipyapp/_version.py'
versioneer.versionfile_build = 'ipyapp/_version.py'
versioneer.tag_prefix = ''
versioneer.parentdir_prefix = 'conda-launch-'


setup(
    name                = "conda-launch",
    version             = versioneer.get_version(),
    author              = "Continuum Analytics, Inc.",
    author_email        = "ijstokes@continuum.io",
    url                 = "https://github.com/conda/conda-launch",
    license             = "BSD",
    description         = "appify ipython notebooks",
    long_description    = open('README.md').read(),
    packages            = ['ipyapp'],
    install_requires    = ['ipython', 'runipy', 'flask', 'requests',
                           'psutil', 'conda', 'conda-api'],

    entry_points        = {'console_scripts':
            ['conda-launch = ipyapp.cli:launchcmd',
             'conda-appserver = ipyapp.cli:startserver']
                            },

    classifiers         = [
        "Development Status :: 4 - Beta",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
                        ],
)
