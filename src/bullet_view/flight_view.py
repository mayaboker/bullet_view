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
        self.land = QtWidgets.QPushButton('Land')
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
        for widget in (self.arm, self.slider, self.height, self.apply, self.start, self.land, self.disarm):
            row.addWidget(widget)
        layout.addLayout(row)
        self.state_label = QtWidgets.QLabel()
        self.mode_label = QtWidgets.QLabel()
        self.result_label = QtWidgets.QLabel()
        self.availability_label = QtWidgets.QLabel()
        self.availability_label.setWordWrap(True)
        layout.addWidget(self.state_label)
        layout.addWidget(self.mode_label)
        layout.addWidget(self.availability_label)
        layout.addWidget(self.result_label)
        self.slider.valueChanged.connect(lambda value: self.height.setValue(value / HEIGHT_SLIDER_SCALE))
        self.height.valueChanged.connect(self._draft_changed)
        self.arm.clicked.connect(lambda: presenter.request_flight('arm'))
        self.start.clicked.connect(lambda: presenter.request_flight('start', self.height.value()))
        self.land.clicked.connect(lambda: presenter.request_flight('land'))
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
        if not remote.valid or remote.readiness == FLYING or self.snapshot.pending in ('arm', 'start'):
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
        land_reason = flight_action_block_reason(snapshot, 'land')
        self.arm.setEnabled(arm_reason is None)
        self.arm.setToolTip(arm_reason or 'Arm at minimum throttle; wait for armed idle')
        editable = free and idle and snapshot.mode == 'manual'
        self.slider.setEnabled(editable)
        self.height.setEnabled(editable)
        self.apply.setEnabled(editable)
        self.start.setEnabled(start_reason is None)
        self.start.setText('Takeoff' if snapshot.mode == 'manual' else 'Start auto mission')
        self.start.setToolTip(start_reason or 'Start takeoff using the confirmed height')
        self.land.setEnabled(land_reason is None)
        self.land.setToolTip(land_reason or 'Land and disarm')
        disarm_available = (snapshot.control_available and remote.target is not None
                            and (remote.armed is True or snapshot.pending in ('arm', 'start')
                                 or not remote.valid))
        self.disarm.setEnabled(disarm_available)
        self.availability_label.setText(f'Arm: {arm_reason or "ready"} · Start: {start_reason or "ready"} · Land: {land_reason or "ready"}')
        self.mode_label.setText(f'App mode: {snapshot.mode} · Phase: {snapshot.phase}')
        arm = 'unknown' if remote.armed is None or not remote.valid else 'armed' if remote.armed else 'disarmed'
        height = 'unknown' if remote.height_m is None else f'{remote.height_m:.1f} m'
        self.state_label.setText(f'Observed: {arm} · Applied height: {height} · {READINESS_TEXT.get(remote.readiness, "unknown")}')
        self.result_label.setText(snapshot.result)
