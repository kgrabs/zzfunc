#!/usr/bin/env python3

import setuptools

with open("README.md") as fh:
    long_description = fh.read()

with open("requirements.txt") as fh:
    install_requires = fh.read()

name = "zzfunc"
version = "1.0.0"
release = "1.0.0"

setuptools.setup(
    name=name,
    version=release,
    author="kgrabs",
    description="I made this",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["zzfunc"],
    url="https://github.com/kgrabs/zzfunc",
    package_data={
        'zzfunc': ['py.typed'],
    },
    install_requires=install_requires,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',
)
