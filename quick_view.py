"""Minimal image viewer — subscribes to SHM camera frames, shows them in a window.

No bullet_msgs dependency. Run from bullet_view's venv:
    uv run python quick_view.py --image-endpoint tcp://127.0.0.1:5556
"""
import argparse
import sys

import zmq
from PySide6 import QtCore, QtGui, QtWidgets

from bullet_image_transport.shm import FrameReader, MAX_MESSAGE_BYTES, topic_prefix

IMAGE_TOPIC = 'camera/front/image'
POLL_TIMEOUT_MS = 50


class Viewer(QtWidgets.QMainWindow):
    def __init__(self, endpoint):
        super().__init__()
        self.setWindowTitle('Bullet Quick View')
        self.label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.label.setMinimumSize(640, 480)
        self.setCentralWidget(self.label)
        self.status = self.statusBar()
        self.frames = 0

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.setsockopt(zmq.CONFLATE, 1)
        self.socket.setsockopt(zmq.MAXMSGSIZE, MAX_MESSAGE_BYTES)
        self.socket.setsockopt(zmq.SUBSCRIBE, topic_prefix(IMAGE_TOPIC))
        self.socket.connect(endpoint)
        self.reader = FrameReader(IMAGE_TOPIC)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(16)

    def poll(self):
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        while self.socket in dict(poller.poll(0)):
            try:
                result = self.reader.read(self.socket.recv(zmq.NOBLOCK))
            except (ValueError, OSError, zmq.ZMQError):
                continue
            if result is None:
                continue
            metadata, pixels = result
            w, h, step = metadata['width'], metadata['height'], metadata['step']
            row_bytes = w * 3
            if step != row_bytes:
                pixels = b''.join(pixels[offset:offset + row_bytes]
                                  for offset in range(0, step * h, step))
            else:
                pixels = bytes(pixels)
            image = QtGui.QImage(pixels, w, h, row_bytes, QtGui.QImage.Format_RGB888)
            image._pixel_data = pixels
            self.label.setPixmap(QtGui.QPixmap.fromImage(image).scaled(
                self.label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            self.frames += 1
            fid = metadata.get('header', {}).get('fid', '?')
            self.status.showMessage(f'frame {self.frames}  fid={fid}  {w}x{h}')

    def closeEvent(self, event):
        self.timer.stop()
        self.reader.close()
        self.socket.close(linger=0)
        self.context.term()
        super().closeEvent(event)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--image-endpoint', default='tcp://127.0.0.1:5556')
    args = parser.parse_args()
    app = QtWidgets.QApplication(sys.argv)
    viewer = Viewer(args.image_endpoint)
    viewer.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
