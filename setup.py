# -*- coding: utf-8 -*-

# Learn more: https://github.com/kennethreitz/setup.py

from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

with open('requirements.txt') as f:
    requirements = f.read()

setup(
    name='passive-data-kit-client',
    version='0.1.0',
    description='Client library for interacting with Passive Data Kit servers',
    long_description=readme,
    author='Chris J. Karr',
    author_email='chris@audacious-software.com',
    url='https://github.com/audaciouscode/PassiveDataKit-Client-Python',
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),
	install_requires=requirements.strip().split('\n'),
)

