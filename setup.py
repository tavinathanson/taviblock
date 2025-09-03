#!/usr/bin/python3
from setuptools import setup, find_packages

setup(
    name="taviblock",
    version="2.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "PyYAML>=6.0",
    ],
    entry_points={
        'console_scripts': [
            'taviblock=cli.taviblock:main',
        ],
    },
    python_requires=">=3.8",
    description="Domain blocking tool with flexible YAML-based profiles",
    author="Your Name",
    package_data={
        '': ['*.yaml', '*.yml', '*.txt'],
    },
)