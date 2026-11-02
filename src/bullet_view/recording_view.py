"""Recording widgets; presenter and worker own communication."""
from PySide6 import QtWidgets
from bullet_msgs.mavlink_control import RECORDING_AUTH_MAVLINK, RECORDING_AUTH_GODOT
from .recording_control import RecordingSnapshot


class RecordingPanel(QtWidgets.QGroupBox):
    def __init__(self, presenter):
        super().__init__('Recording')
        self.presenter = presenter
        layout = QtWidgets.QHBoxLayout(self)
        self.start = QtWidgets.QPushButton('Start recording')
        self.stop = QtWidgets.QPushButton('Stop recording')
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.start)
        layout.addWidget(self.stop)
        layout.addWidget(self.status, 1)
        self.start.clicked.connect(lambda: presenter.request_recording(True))
        self.stop.clicked.connect(lambda: presenter.request_recording(False))
        if hasattr(presenter, 'recording_changed'):
            presenter.recording_changed.connect(self.set_snapshot)
        self.set_snapshot(RecordingSnapshot())

    def set_snapshot(self, snapshot):
        controllable = (snapshot.control_available and snapshot.authority == RECORDING_AUTH_MAVLINK
                        and snapshot.target is not None)
        self.start.setEnabled(controllable and snapshot.online and snapshot.pending is None
                              and snapshot.state in ('idle', 'error'))
        self.stop.setEnabled(controllable and snapshot.pending != 'stop')
        authority = ('MAVLink' if snapshot.authority == RECORDING_AUTH_MAVLINK else
                     'Godot (use Godot recording controls)' if snapshot.authority == RECORDING_AUTH_GODOT else 'unavailable')
        state = snapshot.state if snapshot.online else 'unknown / disconnected'
        self.status.setText(f'Recorder: {state} · Control: {authority} · {snapshot.result}')
