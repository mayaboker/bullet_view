"""Local renderer image subscription and bounded fid matching."""

from collections import OrderedDict
from threading import Event

from PySide6 import QtCore
import zmq
from bullet_image_transport.shm import FrameReader, MAX_MESSAGE_BYTES, topic_prefix

from .model import ImageFrame


IMAGE_TOPIC = 'camera/front/image'
MAX_CACHED_FRAMES = 30
BBOX_STALE_S = .5
POLL_TIMEOUT_MS = 50


def image_frame_from_shm(metadata, pixels):
    width, height, step = (metadata[key] for key in ('width', 'height', 'step'))
    row_bytes = width * 3
    if step != row_bytes:
        pixels = b''.join(pixels[offset:offset + row_bytes]
                          for offset in range(0, step * height, step))
    fid = metadata.get('header', {}).get('fid', metadata['sequence'])
    return ImageFrame(width, height, metadata['encoding'], pixels,
                      metadata['sequence'], metadata['capture_ns'], fid, metadata['session'])


class ImageWorker(QtCore.QObject):
    frame = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, endpoint):
        super().__init__()
        self.endpoint = endpoint
        self.stop_requested = Event()

    def request_stop(self):
        self.stop_requested.set()

    @QtCore.Slot()
    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        reader = FrameReader(IMAGE_TOPIC)
        try:
            socket.setsockopt(zmq.LINGER, 0)
            socket.setsockopt(zmq.CONFLATE, 1)
            socket.setsockopt(zmq.MAXMSGSIZE, MAX_MESSAGE_BYTES)
            socket.setsockopt(zmq.SUBSCRIBE, topic_prefix(IMAGE_TOPIC))
            socket.connect(self.endpoint)
            poller = zmq.Poller()
            poller.register(socket, zmq.POLLIN)
            while not self.stop_requested.is_set():
                if socket not in dict(poller.poll(POLL_TIMEOUT_MS)):
                    continue
                try:
                    result = reader.read(socket.recv(zmq.NOBLOCK))
                    if result is None:
                        continue
                    metadata, pixels = result
                    self.frame.emit(image_frame_from_shm(metadata, pixels))
                except (ValueError, OSError, zmq.ZMQError) as error:
                    self.failed.emit(f'Camera frame skipped: {error}')
        except (OSError, zmq.ZMQError) as error:
            self.failed.emit(f'Camera connection failed: {error}')
        finally:
            reader.close()
            socket.close(linger=0)
            context.term()
            self.finished.emit()


class FrameMatcher:
    def __init__(self):
        self.frames = OrderedDict()
        self.pending = OrderedDict()
        self.session = None
        self.latest = None
        self.last_bbox_at = None

    def add_frame(self, frame, now):
        if frame.session != self.session:
            self.frames.clear()
            if self.session is not None:
                self.pending.clear()
                self.last_bbox_at = None
            self.session = frame.session
        self.latest = frame
        self.frames[frame.fid] = frame
        if len(self.frames) > MAX_CACHED_FRAMES:
            self.frames.popitem(last=False)
        box = self.pending.pop(frame.fid, None)
        if box is not None:
            return self._pair(frame, box)
        if self.last_bbox_at is None or now - self.last_bbox_at > BBOX_STALE_S:
            return frame, None
        return None

    def add_bbox(self, box, now):
        self.last_bbox_at = now
        frame = self.frames.get(box.fid)
        if frame is not None:
            return self._pair(frame, box)
        self.pending[box.fid] = box
        if len(self.pending) > MAX_CACHED_FRAMES:
            self.pending.popitem(last=False)
        return None

    def fallback(self, now):
        if (self.latest is not None and self.last_bbox_at is not None
                and now - self.last_bbox_at > BBOX_STALE_S):
            self.last_bbox_at = None
            return self.latest, None
        return None

    @staticmethod
    def _pair(frame, box):
        if box.valid and (box.x < 0 or box.y < 0 or box.width <= 0 or box.height <= 0
                          or box.x + box.width > frame.width or box.y + box.height > frame.height):
            return frame, None
        return frame, box if box.valid else None
