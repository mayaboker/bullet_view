"""Mission approval and abort controls; network IO stays in the worker."""
from PySide6 import QtCore, QtWidgets
from .flight_protocol import (MIN_TAKEOFF_HEIGHT_M, MAX_TAKEOFF_HEIGHT_M,
                              DEFAULT_TAKEOFF_HEIGHT_M, FLYING, HEIGHT_STEP_M)
from .flight_control import FlightSnapshot, flight_action_block_reason

HEIGHT_SLIDER_SCALE = 10
MIN_APPLIED_HEIGHT_M = MIN_TAKEOFF_HEIGHT_M
MAX_SLIDER_HEIGHT_M = MAX_TAKEOFF_HEIGHT_M

READINESS_TEXT = {0: 'unavailable / prearm checks pending', 1: 'disarmed idle',
                  2: 'armed idle', 3: 'mission active', 4: 'stop/reset required'}


class FlightPanel(QtWidgets.QGroupBox):
    def __init__(self, presenter):
        super().__init__('Flight controls · height above launch')
        self.presenter = presenter
        self.snapshot = FlightSnapshot()
        layout = QtWidgets.QVBoxLayout(self)
        row = QtWidgets.QHBoxLayout()
        self.arm = QtWidgets.QPushButton('Arm')
        self.start = QtWidgets.QPushButton('Start mission')
        self.land = QtWidgets.QPushButton('Land')
        self.disarm = QtWidgets.QPushButton('Disarm')
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setRange(0, round(MAX_SLIDER_HEIGHT_M * HEIGHT_SLIDER_SCALE))
        self.slider.setValue(round(DEFAULT_TAKEOFF_HEIGHT_M * HEIGHT_SLIDER_SCALE))
        self.height = QtWidgets.QDoubleSpinBox()
        self.height.setRange(0, MAX_TAKEOFF_HEIGHT_M)
        self.height.setDecimals(1)
        self.height.setSingleStep(HEIGHT_STEP_M)
        self.height.setSuffix(' m')
        self.height.setValue(DEFAULT_TAKEOFF_HEIGHT_M)
        self.height.setReadOnly(True)
        self.height.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.apply = QtWidgets.QPushButton('Apply height')
        self._height_dirty = False
        self.slider.valueChanged.connect(self._slider_changed)
        self.height.valueChanged.connect(self._height_changed)
        self.apply.clicked.connect(self._apply_height)
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
        self.arm.clicked.connect(lambda: presenter.request_flight('arm'))
        self.start.clicked.connect(lambda: presenter.request_flight('start'))
        self.land.clicked.connect(lambda: presenter.request_flight('land'))
        self.disarm.clicked.connect(self._disarm)
        if hasattr(presenter, 'flight_changed'):
            presenter.flight_changed.connect(self.set_snapshot)
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

    def _slider_changed(self, value):
        self.height.setValue(value / HEIGHT_SLIDER_SCALE)

    def _height_changed(self, value):
        self._height_dirty = True
        with QtCore.QSignalBlocker(self.slider):
            self.slider.setValue(round(value * HEIGHT_SLIDER_SCALE))
        self.set_snapshot(self.snapshot)

    def _apply_height(self):
        self.presenter.request_flight('height', self.height.value())

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
        remote = snapshot.remote
        editable = snapshot.mode == 'manual' and snapshot.mission == 'target-hit'
        if not editable:
            self._height_dirty = False
        height_reason = flight_action_block_reason(snapshot, 'height') if editable else 'Height is fixed by mission profile'
        if snapshot.pending is None and snapshot.result == 'height: ACK accepted and remote state confirmed':
            self._height_dirty = False
        if remote.height_m is not None and not self._height_dirty:
            with QtCore.QSignalBlocker(self.height), QtCore.QSignalBlocker(self.slider):
                self.height.setValue(remote.height_m)
                self.slider.setValue(round(remote.height_m * HEIGHT_SLIDER_SCALE))
        self.height.setReadOnly(not editable)
        self.height.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.UpDownArrows if editable else QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.height.setEnabled(editable and height_reason is None)
        self.slider.setVisible(editable)
        self.apply.setVisible(editable)
        self.slider.setEnabled(editable and height_reason is None)
        self.apply.setEnabled(editable and height_reason is None and self._height_dirty
                              and self.height.value() >= MIN_APPLIED_HEIGHT_M)
        arm_reason = flight_action_block_reason(snapshot, 'arm')
        start_reason = flight_action_block_reason(snapshot, 'start')
        land_reason = flight_action_block_reason(snapshot, 'land')
        self.arm.setEnabled(arm_reason is None)
        self.arm.setToolTip(arm_reason or 'Arm at minimum throttle; wait for armed idle')
        self.start.setEnabled(start_reason is None and not self._height_dirty)
        self.start.setText('Start target mission' if snapshot.mission == 'target-hit' else 'Start hover mission')
        self.start.setToolTip(start_reason or ('Apply height first' if self._height_dirty else 'Start takeoff using the confirmed height'))
        self.land.setEnabled(land_reason is None)
        self.land.setToolTip(land_reason or 'Land and disarm')
        disarm_available = (snapshot.control_available and remote.target is not None
                            and (remote.armed is True or snapshot.pending in ('arm', 'start')
                                 or not remote.valid))
        self.disarm.setEnabled(disarm_available)
        self.availability_label.setText(f'Arm: {arm_reason or "ready"} · Start: {start_reason or "ready"} · Land: {land_reason or "ready"}')
        self.mode_label.setText(f'App mode: {snapshot.mode} · Mission: {snapshot.mission} · '
                                f'Phase: {snapshot.phase} · Result: {snapshot.mission_result}')
        arm = 'unknown' if remote.armed is None or not remote.valid else 'armed' if remote.armed else 'disarmed'
        height = 'unknown' if remote.height_m is None else f'{remote.height_m:.1f} m'
        hover = 'unknown' if snapshot.hover_s is None else f'{snapshot.hover_s:.1f} s'
        self.state_label.setText(f'Observed: {arm} · Configured height: {height} · Hover: {hover} · {READINESS_TEXT.get(remote.readiness, "unknown")}')
        self.result_label.setText(snapshot.result)
