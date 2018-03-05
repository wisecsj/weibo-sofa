# -*- coding: utf-8 -*-


""" 
@author: W@I@S@E 
@contact: wisecsj@gmail.com 
@site: https://wisecsj.github.io 
@file: setup.py.py 
@time: 2018/2/19 21:07 
"""
from setuptools import setup, find_packages

setup(
    name='weibo_sofa',
    version='0.1.8',
    description='Auto-grab sina weibo sofa',
    url='',
    author='wisecsj',
    author_email='wisecsj@gamil.com',
    keywords='sina weibo sofa python',
    packages=find_packages(),
    install_requires=['rsa', 'requests', 'Pillow'],
    python_requires='>=3',
    package_data={'weibo': ['helper']},
    entry_points={
        'console_scripts': [
            'weibo=weibo.cli:main',
        ],
    },

)
