# -*- coding: utf-8 -*-
import base64
import cv2
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import multiprocessing
import numpy as np
import os


# logging
from logging import getLogger, NullHandler, CRITICAL
logger = getLogger(__name__)
logger.addHandler(NullHandler())

# disable werkzeug logger
werkzeug_logger = getLogger('werkzeug')
werkzeug_logger.setLevel(CRITICAL)
# disable werkzeug logger
engineio_logger = getLogger('engineio')
engineio_logger.setLevel(CRITICAL)
# disable socketio logger
socketio_logger = getLogger('socketio')
socketio_logger.setLevel(CRITICAL)


IO_NAMESPACE = '/uploader'


def decodeimg(img):
    '''decode from jpg/png base64 string image'''
    try:
        img = img[img.find(',') + 1:]
        img = base64.decodestring(img.encode('ascii'))
        img = np.fromstring(img, dtype=np.uint8)
        img = cv2.imdecode(img, 1)
        return img
    except Exception:
        logger.error('Failed to decodeimg()')
        return None


def encodeimg(img, ext='.jpeg'):
    try:
        ret, img = cv2.imencode(ext, img)
        if not ret:
            raise
        img = img.tostring()
        img = base64.encodestring(img)
        img = 'data:image/jpeg;base64,' + img.decode('ascii')
        return img
    except Exception:
        logger.error('Failed to encodeimg()')
        return None


def trimming(img, region):
    x, y, w, h = region['x'], region['y'], region['w'], region['h']
    x, y, w, h = int(x), int(y), int(w), int(h)
    if (0 <= x and 0 <= y) and (0 < w and 0 < h) and \
       (x + w < img.shape[1] and y + h < img.shape[0]):
        img = img[y:y + h, x:x + w]
    return img


def encodeImgElement(data, key):
    try:
        img = encodeimg(data[key])
        if img is None:
            raise Exception()
        data[key] = img
    except KeyError:
        logger.error('No image data (key: %s)' % key)
    except:
        logger.error('Invalid image data (key: %s)' % key)
        try:
            data.pop(key)
        except:
            pass


def new_server(request_queue, response_queue, stop_page, port, secret_key):
    # create server
    app = Flask(__name__, static_url_path='/static')
    app.config['SECRET_KEY'] = secret_key
    socketio = SocketIO(app, async_mode='threading',
                        logger=False, engineio_logger=False)

    # rooting
    @app.route('/')
    def __index():
        logger.info('Render uploader page')
        return render_template('index.html', script="index.js")

    if stop_page:
        @app.route('/stop')
        def __stop():
            socketio.stop()
            logger.info('Server stop request')
            return 'This server is stopped'

    @socketio.on('connect', namespace=IO_NAMESPACE)
    def __on_upload_connect():
        logger.info('New uploader connection is established')

    @socketio.on('disconnect', namespace=IO_NAMESPACE)
    def __on_upload_disconnect():
        logger.info('Uploader connection is closed')

    @socketio.on('upload_img', namespace=IO_NAMESPACE)
    def __on_upload_image(data):
        logger.info('New image is received')
        # check need to output
        if request_queue is None:
            return

        # decode from jpeg base64 string
        try:
            img = data['img']
        except KeyError:
            logger.error('Invalid data type')
            return
        img = decodeimg(img)
        if img is None:
            return

        # trimming
        try:
            region = data['region']
            img = trimming(img, region)
        except KeyError:
            pass

        # put into output queue
        request_queue.put(img)

        # emit response
        if response_queue is not None:
            # wait for response
            resp_data = response_queue.get()
            # encode image
            encodeImgElement(resp_data, key='img')
            # emit
            logger.info('Emit response')
            emit('response', resp_data, namespace=IO_NAMESPACE)

    # start server
    logger.info('Start server on port %d' % port)
    socketio.run(app, host='0.0.0.0', port=port, debug=False, log_output=False)
    logger.info('Stop server on port %d' % port)


def start(request_queue, response_queue=None, stop_page=True, port=5000,
          secret_key=os.urandom(24)):
    '''Start new image uploading server on `port`.
    This function create new daemon process and start it.

    arguments:
        * request_queue (multiprocessing.Queue): output queue.
            It returns a image (np.ndarray).
        * response_queue (multiprocessing.Queue): input queue.
            The input type is dict and it can contain
            'img': (np.ndarray), 'img_options': {'region': (bool)},
            'msg': (str).
        * stop_page (bool): enable server stop page "/stop".
        * port (int): server port

    If there are no need to use IO, set corresponding queues to `None`.
    '''
    process = multiprocessing.Process(target=new_server,
                                      args=(request_queue, response_queue,
                                            stop_page, port, secret_key))
    process.daemon = True
    process.start()
