"""Persistent manual controls; all network IO stays in the worker."""
from PySide6 import QtCore, QtWidgets
from bullet_msgs.spawn import MIN_TAKEOFF_HEIGHT_M, MAX_TAKEOFF_HEIGHT_M, DEFAULT_TAKEOFF_HEIGHT_M
from bullet_msgs.flight_control import (DISARMED_IDLE, ARMED_IDLE, FLYING,
    HEIGHT_STEP_M)
from .flight_control import FlightSnapshot, flight_action_block_reason

HEIGHT_SLIDER_SCALE = 10
READINESS_TEXT = {0: 'unavailable / prearm checks pending', 1: 'disarmed idle',
                  2: 'armed idle', 3: 'mission active', 4: 'stop/reset required'}


class FlightPanel(QtWidgets.QGroupBox):
    def __init__(self, presenter):
        super().__init__('Flight controls · height above launch')
        self.presenter = presenter
        self.snapshot = FlightSnapshot()
        self.draft_edited = False
        self.initialized = False
        layout = QtWidgets.QVBoxLayout(self)
        row = QtWidgets.QHBoxLayout()
        self.arm = QtWidgets.QPushButton('Arm')
        self.start = QtWidgets.QPushButton('Start mission')
        self.disarm = QtWidgets.QPushButton('Disarm')
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(round(MIN_TAKEOFF_HEIGHT_M * HEIGHT_SLIDER_SCALE), round(MAX_TAKEOFF_HEIGHT_M * HEIGHT_SLIDER_SCALE))
        self.height = QtWidgets.QDoubleSpinBox()
        self.height.setRange(MIN_TAKEOFF_HEIGHT_M, MAX_TAKEOFF_HEIGHT_M)
        self.height.setDecimals(1)
        self.height.setSingleStep(HEIGHT_STEP_M)
        self.height.setSuffix(' m')
        self.height.setValue(DEFAULT_TAKEOFF_HEIGHT_M)
        self.slider.setValue(round(DEFAULT_TAKEOFF_HEIGHT_M * HEIGHT_SLIDER_SCALE))
        self.apply = QtWidgets.QPushButton('Apply height')
        for widget in (self.arm, self.slider, self.height, self.apply, self.start, self.disarm):
            row.addWidget(widget)
        layout.addLayout(row)
        self.state_label = QtWidgets.QLabel()
        self.result_label = QtWidgets.QLabel()
        self.availability_label = QtWidgets.QLabel()
        self.availability_label.setWordWrap(True)
        layout.addWidget(self.state_label)
        layout.addWidget(self.availability_label)
        layout.addWidget(self.result_label)
        self.slider.valueChanged.connect(lambda value: self.height.setValue(value / HEIGHT_SLIDER_SCALE))
        self.height.valueChanged.connect(self._draft_changed)
        self.arm.clicked.connect(lambda: presenter.request_flight('arm'))
        self.start.clicked.connect(lambda: presenter.request_flight('start', self.height.value()))
        self.apply.clicked.connect(lambda: presenter.request_flight('height', self.height.value()))
        self.disarm.clicked.connect(self._disarm)
        if hasattr(presenter, 'flight_changed'):
            presenter.flight_changed.connect(self.set_snapshot)
        self.set_snapshot(self.snapshot)

    def _draft_changed(self, value):
        self.draft_edited = True
        self.slider.setValue(round(value * HEIGHT_SLIDER_SCALE))
        self.set_snapshot(self.snapshot)

    def _disarm(self):
        remote = self.snapshot.remote
        if not remote.valid or remote.readiness == FLYING or self.snapshot.pending == 'start':
            answer = QtWidgets.QMessageBox.warning(self, 'Emergency disarm',
                'Immediately stop motors and abort the mission? The vehicle may fall.',
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel)
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            self.presenter.request_flight('emergency')
        else:
            self.presenter.request_flight('disarm')

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
        remote = snapshot.remote
        if remote.height_m is not None and not self.initialized and not self.draft_edited:
            self.initialized = True
            with QtCore.QSignalBlocker(self.height), QtCore.QSignalBlocker(self.slider):
                self.height.setValue(remote.height_m)
                self.slider.setValue(round(remote.height_m * HEIGHT_SLIDER_SCALE))
        idle = (snapshot.control_available and remote.valid and remote.target is not None
                and ((remote.readiness == DISARMED_IDLE and remote.armed is False)
                     or (remote.readiness == ARMED_IDLE and remote.armed is True)))
        free = snapshot.pending is None
        arm_reason = flight_action_block_reason(snapshot, 'arm')
        start_reason = flight_action_block_reason(snapshot, 'start', self.height.value())
        self.arm.setEnabled(arm_reason is None)
        self.arm.setToolTip(arm_reason or 'Arm at minimum throttle; wait for armed idle')
        self.slider.setEnabled(free and idle)
        self.height.setEnabled(free and idle)
        self.apply.setEnabled(free and idle)
        self.start.setEnabled(start_reason is None)
        self.start.setToolTip(start_reason or 'Start takeoff using the confirmed height')
        self.disarm.setEnabled(snapshot.control_available and remote.target is not None)
        self.availability_label.setText(f'Arm: {arm_reason or "ready"} · Start: {start_reason or "ready"}')
        arm = 'unknown' if remote.armed is None or not remote.valid else 'armed' if remote.armed else 'disarmed'
        height = 'unknown' if remote.height_m is None else f'{remote.height_m:.1f} m'
        self.state_label.setText(f'Observed: {arm} · Applied height: {height} · {READINESS_TEXT.get(remote.readiness, "unknown")}')
        self.result_label.setText(snapshot.result)
