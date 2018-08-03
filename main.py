#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import log_initializer

import cv2
from logging import getLogger, DEBUG, INFO, WARNING
import multiprocessing
import time
import datetime
import os
try:
    import Queue  # python2
except:
    import queue as Queue  # python3

import imguploader

# logging
log_initializer.setFmt()
log_initializer.setRootLevel(WARNING)
logger = getLogger(__name__)
logger.setLevel(DEBUG)
imguploader.logger.setLevel(INFO)


if __name__ == '__main__':
    logger.info('Start')

    request_queue = multiprocessing.Queue()
    response_queue = multiprocessing.Queue()

    imguploader.start(request_queue, response_queue, stop_page=True, port=5000)

    while True:
        try:
            # wait for image uploading
            img = request_queue.get(block=False)

            # save image
            os.makedirs('out', exist_ok=True)
            cv2.imwrite('out/{}.jpg'.format(datetime.datetime.now()), img)

            # must be response
            res_message = 'message ' + str(time.time())
            response_queue.put({'img': img,
                                'img_options': {'region': True},
                                'msg': res_message})
        except Queue.Empty:
            pass
