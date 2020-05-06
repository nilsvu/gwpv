#!/usr/bin/env python

from distutils.core import setup

with open('README.md', 'r') as readme_file:
    long_description = readme_file.read()

setup(
    name='gwpv',
    version='0.1.0',
    description="Visualize gravitational waves with ParaView",
    author="Nils L. Fischer",
    author_email="nils.fischer@aei.mpg.de",
    url="https://github.com/nilsleiffischer/gwpv",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=[
        'gwpv', 'gwpv.plugin_util', 'gwpv.render', 'gwpv.scene_configuration'
    ],
    scripts=['scripts/gwrender.py'],
    package_data={
        'gwpv': [
            '../scene_overrides/*.yaml', '../scene_overrides/**/*.yaml',
            '../paraview_plugins/*.py'
        ],
    },
    install_requires=[
        'numpy', 'scipy', 'h5py', 'spherical_functions', 'numba', 'pyyaml',
        'tqdm'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 2.7",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
