import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6 import QtCore, QtWidgets
import socket
import time

from bullet_simulation_protocol.requests import OperationReply
from bullet_simulation_protocol.state import SimulationState
from bullet_simulation_protocol.transport import ZmqIo
from bullet_view.presenter import Presenter
from bullet_view.simulation_control import SimulationSnapshot, SimulationWorker
from bullet_view.simulation_view import SimulationPanel


def state(value, revision=0, session='a' * 32):
    return SimulationState(1, 'drone_1', session, 'episode', value, revision)


def test_presenter_uses_fresh_ordered_state_for_commands():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    clock = [100.]
    presenter = Presenter('udpin:127.0.0.1:14550', clock=lambda: clock[0])
    presenter.simulation_thread.start()
    try:
        assert presenter.request_simulation('stop') is False
        presenter._on_simulation_state(state('running', 2), 100.)
        presenter._on_simulation_state(state('stopped_ready', 1), 100.1)
        assert presenter.simulation_snapshot.state.state == 'running'
        assert presenter.request_simulation('stop') is True
        assert presenter.request_simulation('reset') is False
        if not presenter.simulation_worker.commands.empty():
            presenter.simulation_worker.commands.get_nowait()
        presenter._on_simulation_result('stop', 'success', '')
        clock[0] = 103.
        presenter._refresh_freshness()
        assert not presenter.simulation_snapshot.fresh
        assert presenter.request_simulation('stop') is False
        presenter._on_simulation_state(state('stopped_ready', 0, 'b' * 32), 103.)
        assert presenter.request_simulation('start') is True
    finally:
        presenter.stop()
        app.processEvents()


def test_panel_enables_actions_and_shows_reply_modals(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    del app

    class FakePresenter(QtCore.QObject):
        simulation_changed = QtCore.Signal(object)
        simulation_result = QtCore.Signal(str, str, str)
        simulation_snapshot = SimulationSnapshot()

        def __init__(self):
            super().__init__()
            self.actions = []

        def request_simulation(self, action):
            self.actions.append(action)
            return True

    messages = []
    monkeypatch.setattr(QtWidgets.QMessageBox, 'information',
                        lambda *args: messages.append(('success', args[-1])))
    monkeypatch.setattr(QtWidgets.QMessageBox, 'warning',
                        lambda *args: messages.append(('warning', args[-1])))
    presenter = FakePresenter()
    panel = SimulationPanel(presenter)
    try:
        assert not any(button.isEnabled() for button in (panel.start, panel.stop, panel.reset))
        presenter.simulation_changed.emit(SimulationSnapshot(state('running'), True))
        assert panel.stop.isEnabled() and not panel.start.isEnabled() and not panel.reset.isEnabled()
        panel.stop.click()
        assert presenter.actions == ['stop']
        presenter.simulation_changed.emit(SimulationSnapshot(state('stopped_ready'), True))
        assert panel.start.isEnabled() and panel.reset.isEnabled() and not panel.stop.isEnabled()
        presenter.simulation_result.emit('reset', 'success', '')
        presenter.simulation_result.emit('start', 'failure', 'reset_required')
        presenter.simulation_result.emit('stop', 'unknown', 'No reply')
        assert messages[0][0] == 'success' and 'Restart Bullet App' in messages[0][1]
        assert messages[1] == ('warning', 'Start failed: reset_required')
        assert messages[2][0] == 'warning' and 'Outcome unknown' in messages[2][1]
    finally:
        panel.close()


def test_restart_button_requires_stopped_simulation_and_fresh_app_status(monkeypatch):
    from bullet_view.flight_control import FlightSnapshot

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    del app

    class Presenter(QtCore.QObject):
        simulation_changed = QtCore.Signal(object)
        flight_changed = QtCore.Signal(object)
        app_restart_result = QtCore.Signal(str, str)
        simulation_snapshot = SimulationSnapshot()
        flight_snapshot = FlightSnapshot()

        def __init__(self):
            super().__init__()
            self.calls = 0

        def request_app_restart(self):
            self.calls += 1

    presenter = Presenter()
    panel = SimulationPanel(presenter)
    try:
        ready = SimulationSnapshot(state('stopped_ready'), True)
        presenter.simulation_snapshot = ready
        panel.set_snapshot(ready)
        assert not panel.restart_app.isEnabled()
        fresh = FlightSnapshot(mode='manual', app_state='restart_required',
                               app_status_at_s=time.monotonic())
        panel.set_flight_snapshot(fresh)
        assert panel.restart_app.isEnabled()
        panel.restart_app.click()
        assert presenter.calls == 1
        panel.set_flight_snapshot(FlightSnapshot(mode='manual', app_state='restart_required',
                                                 app_status_at_s=time.monotonic() - 2.))
        assert not panel.restart_app.isEnabled()
        presenter.simulation_snapshot = SimulationSnapshot(state('running'), True)
        panel.set_snapshot(presenter.simulation_snapshot)
        panel.set_flight_snapshot(fresh)
        assert not panel.restart_app.isEnabled()
    finally:
        panel.close()


def test_simulation_worker_receives_state_and_command_reply_over_zmq():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def free_endpoint():
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            return f'tcp://127.0.0.1:{probe.getsockname()[1]}'

    state_endpoint, control_endpoint = free_endpoint(), free_endpoint()
    observed, results = [], []
    worker = SimulationWorker(control_endpoint, state_endpoint)
    thread = QtCore.QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.observed.connect(lambda value, received: observed.append(value))
    worker.result.connect(lambda *value: results.append(value))
    worker.finished.connect(thread.quit)
    with ZmqIo(publish_endpoint=state_endpoint, reply_endpoint=control_endpoint) as server:
        thread.start()
        try:
            deadline = time.monotonic() + 3.
            while not observed and time.monotonic() < deadline:
                server.publish(b'simulation/drone_1/state', state('running'))
                app.processEvents()
                time.sleep(.02)
            assert observed and observed[-1].state == 'running'
            assert worker.request('stop')
            while not results and time.monotonic() < deadline:
                if request := server.poll_request():
                    assert request['payload']['payload']['action'] == 'stop'
                    server.reply(request['token'], OperationReply(True))
                app.processEvents()
                time.sleep(.02)
            assert results == [('stop', 'success', '')]
        finally:
            worker.request_stop()
            thread.quit()
            assert thread.wait(2000)
