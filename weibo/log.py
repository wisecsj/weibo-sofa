# -*- coding: utf-8 -*-


"""
    log module
    ~~~~~~~~~~

@author: W@I@S@E 
@contact: wisecsj@gmail.com 
@site: https://wisecsj.github.io 
@file: log.py 
@time: 2018/2/19 20:55 
"""

import logging
import sys
import os


LOGFILE_PATH = os.path.join(os.path.dirname(sys.argv[0]), 'weibo.log')
# logger Stream handler level
DEBUG = False

logger = logging.getLogger('Weibo')
logger.setLevel(logging.DEBUG)

# ~~~~~~~~~~~~~~~
# Todo: email handler
handlers = []
f_handler = logging.FileHandler(LOGFILE_PATH, encoding='utf-8')
f_handler.setLevel(logging.WARNING)
handlers.append(f_handler)

p_handler = logging.StreamHandler(stream=sys.stdout)
p_handler.setLevel(logging.DEBUG if DEBUG else logging.INFO)
handlers.append(p_handler)
# ~~~~~~~~~~~~~~~

# ~~~~~~~~~~~~~~~
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# ~~~~~~~~~~~~~~~

for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)
