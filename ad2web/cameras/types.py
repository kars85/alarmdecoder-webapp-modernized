# -*- coding: utf-8 -*-

import os
import logging
from flask import current_app

try:
    import cv2
    import numpy as np
    from urllib.request import urlopen  # Python 3
    hascv2 = True
except ImportError:
    import cv2
    import numpy as np
    from urllib.request import urlopen
    hascv2 = False

from .models import Camera
from .constants import USERNAME, PASSWORD, JPG_URL, CAMDIR, HEAD, FOOT, RECT_XML_FILE, READ_BYTE_AMOUNT

logger = logging.getLogger(__name__)


class CameraSystem:
    def __init__(self):
        self._cameras = {}
        self._camera_ids = []
        self._image_bytes = {}
        self._xml_path = os.path.join(os.getcwd(), 'ad2web', 'cameras', RECT_XML_FILE)
        self._init_cameras()

    def _init_cameras(self):
        for cam in Camera.query.all():
            self._cameras[cam.id] = [cam.username, cam.password, cam.get_jpg_url]
            self._image_bytes[cam.id] = b''  # store as bytes
            self._camera_ids.append(cam.id)

        current_app.jinja_env.globals['cameras'] = len(self._cameras)

    def get_camera_ids(self):
        return self._camera_ids

    def refresh_camera_ids(self):
        self._camera_ids.clear()
        self._cameras.clear()
        self._image_bytes.clear()
        self._init_cameras()

    def write_image(self, cam_id):
        if not hascv2:
            logger.warning("OpenCV (cv2) is not available. Skipping camera image write.")
            return

        try:
            username = self._cameras[cam_id][USERNAME]
            password = self._cameras[cam_id][PASSWORD]
            url = self._cameras[cam_id][JPG_URL]

            user_pass = f"{username}:{password}@"
            url_slash_index = url.find('//')
            if url_slash_index == -1:
                logger.error(f"Invalid camera URL: {url}")
                return

            stream_url = f"{url[:url_slash_index+2]}{user_pass}{url[url_slash_index+2:]}"
            stream = urlopen(stream_url)
            cascade = cv2.CascadeClassifier(self._xml_path)

            # Read camera stream into buffer until JPEG is complete
            while FOOT not in self._image_bytes[cam_id]:
                self._image_bytes[cam_id] += stream.read(READ_BYTE_AMOUNT)

            head = self._image_bytes[cam_id].find(HEAD)
            foot = self._image_bytes[cam_id].find(FOOT)

            if head != -1 and foot != -1:
                jpg_data = self._image_bytes[cam_id][head:foot + len(FOOT)]
                self._image_bytes[cam_id] = b''  # reset buffer

                # Decode and process image
                img = cv2.imdecode(np.frombuffer(jpg_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    rects = cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5, minSize=(10, 10))

                    for x, y, w, h in rects:
                        cv2.rectangle(img, (x, y), (x + w, y + h), (127, 255, 0), 1)

                    os.makedirs(CAMDIR, exist_ok=True)
                    output_path = os.path.join(CAMDIR, f"cam{cam_id}.jpg")
                    cv2.imwrite(output_path, img)
                else:
                    logger.warning("cv2 failed to decode image bytes.")

        except Exception as e:
            logger.error(f"Error writing camera image for ID {cam_id}: {e}", exc_info=True)
