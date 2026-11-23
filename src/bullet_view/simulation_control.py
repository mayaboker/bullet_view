"""Background ZeroMQ client and immutable simulation UI state."""
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event
import time

from PySide6 import QtCore

from bullet_simulation_protocol.requests import CommandPayload, CommandRequest, OperationReply
from bullet_simulation_protocol.state import STATE_TOPIC, SimulationState
from bullet_simulation_protocol.transport import ZmqIo, decode


WORKER_POLL_S = 0.02
COMMAND_TIMEOUT_S = 2.0
RESET_TIMEOUT_S = 30.0
STATE_STALE_S = 2.0
COMMANDS = frozenset(('start', 'stop', 'reset'))


@dataclass(frozen=True)
class SimulationSnapshot:
    state: SimulationState | None = None
    fresh: bool = False
    pending: str | None = None


class SimulationWorker(QtCore.QObject):
    observed = QtCore.Signal(object, float)
    result = QtCore.Signal(str, str, str)
    failed = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, control_endpoint, state_endpoint):
        super().__init__()
        self.control_endpoint = control_endpoint
        self.state_endpoint = state_endpoint
        self.commands = Queue(1)
        self.stop_requested = Event()

    def request(self, action):
        if action not in COMMANDS:
            raise ValueError('unknown simulation command')
        try:
            self.commands.put_nowait(action)
        except Full:
            return False
        return True

    def request_stop(self):
        self.stop_requested.set()

    @QtCore.Slot()
    def run(self):
        pending = None
        try:
            with ZmqIo(subscribe_endpoint=self.state_endpoint, topics=(STATE_TOPIC,),
                       request_endpoint=self.control_endpoint) as io:
                while not self.stop_requested.is_set():
                    if io.error:
                        raise RuntimeError(io.error)
                    while (parts := io.receive()) is not None:
                        try:
                            state = SimulationState.from_dict(decode(parts[1]))
                        except (IndexError, ValueError, TypeError, UnicodeError):
                            continue
                        self.observed.emit(state, time.monotonic())
                    if pending is None:
                        try:
                            action = self.commands.get_nowait()
                        except Empty:
                            pass
                        else:
                            request = CommandRequest('drone_1', CommandPayload(action))
                            timeout = RESET_TIMEOUT_S if action == 'reset' else COMMAND_TIMEOUT_S
                            pending = action, io.request(request, timeout_s=timeout)
                    if pending is not None and pending[1].done():
                        action, future = pending
                        pending = None
                        try:
                            reply = OperationReply.from_dict(future.result())
                        except TimeoutError:
                            self.result.emit(action, 'unknown', 'No reply; the command may have run')
                        except Exception as error:
                            self.result.emit(action, 'failure', str(error))
                        else:
                            self.result.emit(action, 'success' if reply.success else 'failure',
                                             reply.reason or '')
                    self.stop_requested.wait(WORKER_POLL_S)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()
