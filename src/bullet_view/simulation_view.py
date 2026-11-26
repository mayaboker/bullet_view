"""Simulation lifecycle controls driven by the launcher's state feed."""
from PySide6 import QtCore, QtWidgets

from .simulation_control import SimulationSnapshot
from .flight_control import app_restart_block_reason, FlightSnapshot
import time


STATE_LABELS = {
    'running': 'Running',
    'stopped_reset_required': 'Stopped · reset required',
    'resetting': 'Resetting',
    'stopped_ready': 'Stopped · ready to start',
    'error': 'Reset failed · retry reset',
}


class SimulationPanel(QtWidgets.QWidget):
    def __init__(self, presenter):
        super().__init__()
        self.presenter = presenter
        layout = QtWidgets.QVBoxLayout(self)
        self.status = QtWidgets.QLabel('Simulation state unavailable')
        layout.addWidget(self.status)
        row = QtWidgets.QHBoxLayout()
        self.start = QtWidgets.QPushButton('Start simulation')
        self.stop = QtWidgets.QPushButton('Stop simulation')
        self.reset = QtWidgets.QPushButton('Reset simulation')
        for action, button in (('start', self.start), ('stop', self.stop), ('reset', self.reset)):
            button.clicked.connect(lambda checked=False, name=action: self.presenter.request_simulation(name))
            row.addWidget(button)
        layout.addLayout(row)
        self.restart_app = QtWidgets.QPushButton('Restart Bullet App')
        if hasattr(self.presenter, 'request_app_restart'):
            self.restart_app.clicked.connect(self.presenter.request_app_restart)
        layout.addWidget(self.restart_app)
        self.reset_app = QtWidgets.QPushButton('Reset App')
        if hasattr(self.presenter, 'request_app_reset'):
            self.reset_app.clicked.connect(self._on_reset_app_clicked)
            self.reset_app.setEnabled(getattr(presenter, 'app_reset_available', False))
        else:
            self.reset_app.setEnabled(False)
        self.reset_app.setToolTip('Kill the running Bullet App process and restart the launch script.')
        layout.addWidget(self.reset_app)
        hint = QtWidgets.QLabel('After reset: Restart Bullet App, Start simulation, then Arm and Start mission.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        if hasattr(presenter, 'simulation_changed'):
            presenter.simulation_changed.connect(self.set_snapshot)
        if hasattr(presenter, 'simulation_result'):
            presenter.simulation_result.connect(self.show_result)
        if hasattr(presenter, 'flight_changed'):
            presenter.flight_changed.connect(self.set_flight_snapshot)
        if hasattr(presenter, 'app_restart_result'):
            presenter.app_restart_result.connect(self.show_app_restart_result)
        if hasattr(presenter, 'app_reset_result'):
            presenter.app_reset_result.connect(self.show_app_reset_result)
        self.flight_snapshot = getattr(presenter, 'flight_snapshot', FlightSnapshot())
        self.set_snapshot(getattr(presenter, 'simulation_snapshot', SimulationSnapshot()))

    @QtCore.Slot(object)
    def set_snapshot(self, snapshot):
        state = snapshot.state.state if snapshot.state else None
        self.status.setText(STATE_LABELS.get(state, 'Simulation state unavailable')
                            if snapshot.fresh else 'Simulation state unavailable or stale')
        available = snapshot.fresh and snapshot.pending is None
        self.start.setEnabled(available and state == 'stopped_ready')
        self.stop.setEnabled(available and state == 'running')
        self.reset.setEnabled(available and state in ('stopped_reset_required', 'stopped_ready', 'error'))
        self._update_restart()

    @QtCore.Slot(object)
    def set_flight_snapshot(self, snapshot):
        self.flight_snapshot = snapshot
        self._update_restart()

    def _update_restart(self):
        simulation = getattr(self.presenter, 'simulation_snapshot', SimulationSnapshot())
        ready = (simulation.fresh and simulation.pending is None and simulation.state is not None
                 and simulation.state.state == 'stopped_ready')
        self.restart_app.setEnabled(hasattr(self.presenter, 'request_app_restart') and ready and app_restart_block_reason(
            self.flight_snapshot, time.monotonic()) is None)

    @QtCore.Slot(str, str)
    def show_app_restart_result(self, outcome, reason):
        if outcome == 'success':
            QtWidgets.QMessageBox.information(self, 'Restart Bullet App',
                'Bullet App is ready and disarmed. Start simulation, then Arm and Start mission.')
        else:
            QtWidgets.QMessageBox.warning(self, 'Restart Bullet App', reason)

    def _on_reset_app_clicked(self):
        self.reset_app.setEnabled(False)
        self.presenter.request_app_reset()

    @QtCore.Slot(str, str)
    def show_app_reset_result(self, outcome, reason):
        self.reset_app.setEnabled(getattr(self.presenter, 'app_reset_available', False))
        if outcome == 'success':
            QtWidgets.QMessageBox.information(self, 'Reset App', reason)
        else:
            QtWidgets.QMessageBox.warning(self, 'Reset App', reason)

    @QtCore.Slot(str, str, str)
    def show_result(self, action, outcome, reason):
        title = f'Simulation {action}'
        if outcome == 'success':
            detail = (f'{action.capitalize()} succeeded.' +
                      (' Restart Bullet App before another flight, then press Start simulation.'
                       if action == 'reset' else ''))
            QtWidgets.QMessageBox.information(self, title, detail)
        elif outcome == 'unknown':
            QtWidgets.QMessageBox.warning(self, title, 'Outcome unknown. ' + reason)
        else:
            QtWidgets.QMessageBox.warning(self, title, f'{action.capitalize()} failed: {reason}')
