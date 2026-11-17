"""A MAVLink UDP listener that replies only to the selected App peer."""
import errno

from pymavlink import mavutil


class AppPeerUDP(mavutil.mavudp):
    def __init__(self, endpoint):
        if not endpoint.startswith('udpin:'):
            raise ValueError('App–View link requires a udpin endpoint')
        super().__init__(endpoint.removeprefix('udpin:'), input=True)
        self.last_sender = None
        self.peer = None

    def recv(self, n=None):
        try:
            data, self.last_sender = self.port.recvfrom(mavutil.UDP_MAX_PACKET_LEN)
        except OSError as error:
            if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK, errno.ECONNREFUSED):
                return b''
            raise
        return data

    def select_sender(self):
        if self.last_sender is not None:
            self.peer = self.last_sender

    def write(self, data):
        if self.peer is None:
            raise ConnectionError('No Bullet App peer has been received')
        self.port.sendto(data, self.peer)
