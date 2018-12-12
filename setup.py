from setuptools import setup, find_packages


setup(
    name='ctapipe-flow',
    author='Jean Jaquemier',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'ctapipe',
        'pyzmq',
        'traitlets',
        'graphviz',
    ]
)
