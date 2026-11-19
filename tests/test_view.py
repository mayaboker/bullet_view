import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6 import QtCore, QtWidgets

from bullet_view.model import Altitude, Attitude, Bbox, ImageFrame, StatusText, TelemetrySnapshot
from bullet_view.view import MainWindow


class FakePresenter(QtCore.QObject):
    snapshot_changed = QtCore.Signal(object)
    status_changed = QtCore.Signal(str)
    endpoint = 'udpin:0.0.0.0:14550'

    def stop(self):
        pass


@pytest.fixture
def application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_view_has_telemetry_and_parameters_tabs_and_renders_snapshot(application):
    presenter = FakePresenter()
    window = MainWindow(presenter)
    try:
        snapshot = TelemetrySnapshot(attitude=Attitude(.1, .2, .3, 10), altitude=Altitude(4., 20),
                                     vertical_speed_m_s=1.25, attitude_hz=49.2, altitude_hz=47.8,
                                     image=ImageFrame(2, 2, 'rgb8', bytes(12), 1, 2),
                                     bbox=Bbox(True, 0., 0., 1., 1.),
                                     messages=(StatusText(1, 6, '[01] ready', 1.),))
        window.set_snapshot(snapshot)
        assert window.tabs.count() == 2
        assert window.tabs.tabText(0) == 'Telemetry'
        assert window.tabs.tabText(1) == 'Parameters'
        assert '+17.2°' in window.yaw.text()
        assert window.altitude.altitude_m == 4.
        assert window.vertical_speed.vertical_speed_m_s == 1.25
        assert 'ATTITUDE 49.2 Hz' in window.upstream_rates.text()
        assert 'ALTITUDE 47.8 Hz' in window.upstream_rates.text()
        assert window.sitl_status.text() == 'SITL status unknown'
        assert window.camera_frame.image is not None
        assert window.camera_frame.bbox == Bbox(True, 0., 0., 1., 1.)
        assert window.image_mode.currentText() == 'Remote'
        assert not window.image_mode.isEnabled()
        assert not window.recording_panel.isEnabled()
        assert not window.parameter_panel.isEnabled()
        assert not window.reload_profile.isEnabled()
        assert window.roll.parentWidget().objectName() == 'attitude_summary'
        assert window.message_log.parentWidget().objectName() == 'status_panel'
        assert window.message_log.count() == 1
        assert window.message_log.item(0).text() == '[— s | frame —] ready'
        window.message_log.itemClicked.emit(window.message_log.item(0))
        assert 'waiting for the application to report readiness' in window.message_details.text()
    finally:
        window.close()


def test_view_shows_sitl_confirmation_states(application):
    window = MainWindow(FakePresenter())
    try:
        for confirmed, expected, rate_source, color in (
                (None, 'SITL status unknown', 'Telemetry', '#9bb0c8'),
                (True, 'SITL confirmed', 'SITL', '#ef6b73'),
                (False, 'SITL not confirmed', 'HW', '#70d6ad')):
            window.set_snapshot(TelemetrySnapshot(sitl_confirmed=confirmed))
            assert window.sitl_status.text() == expected
            assert window.upstream_rates.text().startswith(f'{rate_source} rates')
            assert color in window.upstream_rates.styleSheet()
    finally:
        window.close()


def test_view_keeps_auto_scroll_enabled_after_completion(application):
    presenter = FakePresenter()
    window = MainWindow(presenter)
    try:
        messages = tuple(StatusText(index, 6, text, float(index)) for index, text in (
            (1, '[01] ready'), (30, '[30] mission completed'), (2, '[02] late message')))
        window.set_snapshot(TelemetrySnapshot(messages=messages))
        assert window.auto_scroll.isChecked()
        assert window.message_log.count() == 3
    finally:
        window.close()


def test_view_enables_profile_reload_only_when_stopped(application):
    presenter = FakePresenter()
    window = MainWindow(presenter)
    try:
        window.set_snapshot(TelemetrySnapshot(mission_stopped=False))
        assert not window.reload_profile.isEnabled()
        window.set_snapshot(TelemetrySnapshot(mission_stopped=True))
        assert not window.reload_profile.isEnabled()
    finally:
        window.close()


def log_messages(count):
    return tuple(StatusText(i, 6, f'Message {i}', float(i)) for i in range(count))


def test_auto_scroll_checkbox_preserves_position_and_resumes(application):
    window = MainWindow(FakePresenter())
    window.show()
    try:
        window.set_snapshot(TelemetrySnapshot(messages=log_messages(100)))
        application.processEvents()
        bar = window.message_log.verticalScrollBar()
        assert bar.maximum() > 0 and bar.value() == bar.maximum()
        window.auto_scroll.setChecked(False)
        bar.setValue(bar.maximum() // 2)
        position = bar.value()
        window.set_snapshot(TelemetrySnapshot(messages=log_messages(110)))
        application.processEvents()
        assert bar.value() == position
        bar.setValue(bar.maximum())
        position = bar.value()
        window.set_snapshot(TelemetrySnapshot(messages=log_messages(120)))
        application.processEvents()
        assert bar.value() == position
        completion = StatusText(30, 6, 'COMPLETED: target_hit', 121.)
        window.set_snapshot(TelemetrySnapshot(messages=log_messages(120) + (completion,)))
        application.processEvents()
        assert not window.auto_scroll.isChecked() and bar.value() == position
        window.auto_scroll.setChecked(True)
        application.processEvents()
        assert bar.value() == bar.maximum()
    finally:
        window.close()


def test_clear_log_discards_presenter_history_details_and_keeps_receiving(application):
    from bullet_view.presenter import Presenter
    from bullet_view.model import TelemetryUpdate
    from bullet_view.view import MESSAGE_DETAILS_PLACEHOLDER
    presenter = Presenter('test')
    window = MainWindow(presenter)
    try:
        window.auto_scroll.setChecked(False)
        window.clear_log.click()  # Empty history is safe to clear.
        assert not presenter.snapshot.messages and window.message_log.count() == 0
        message = StatusText(1, 6, '[01] ready', 1.)
        presenter._on_update(TelemetryUpdate('STATUSTEXT', message, 1.))
        window.message_log.setCurrentRow(0)
        window.message_log.itemClicked.emit(window.message_log.item(0))
        assert window.message_details.text() != MESSAGE_DETAILS_PLACEHOLDER
        window.clear_log.click()
        assert not presenter.snapshot.messages
        assert window.message_log.count() == 0 and not window.message_log.selectedItems()
        assert window.message_details.text() == MESSAGE_DETAILS_PLACEHOLDER
        assert not window.auto_scroll.isChecked()
        presenter.snapshot_changed.emit(presenter.snapshot)
        assert window.message_log.count() == 0
        new_message = StatusText(2, 6, '[02] new message', 2.)
        presenter._on_update(TelemetryUpdate('STATUSTEXT', new_message, 2.))
        assert presenter.snapshot.messages == (new_message,)
        assert window.message_log.count() == 1
        assert window.message_log.item(0).text() == '[— s | frame —] new message'
        window.clear_log.click()
        window.auto_scroll.setChecked(True)
        window.clear_log.click()
        assert window.auto_scroll.isChecked()
    finally:
        window.close()


def test_view_renders_simulation_time_camera_frame_and_retains_message_code(application):
    from bullet_msgs.status_messages import status_text_chunks
    window = MainWindow(FakePresenter())
    try:
        text = status_text_chunks(7,'HOVER: settling',simulation_time_s=27.075,image_sequence=4809)[0]
        message = StatusText(7,6,text,1000.,27.075,4809)
        window.set_snapshot(TelemetrySnapshot(messages=(message,)))
        item = window.message_log.item(0)
        assert item.text() == '[27.075 s | frame 4809] HOVER: settling'
        assert '[07]' not in item.text()
        window.message_log.itemClicked.emit(item)
        assert 'Message code: 07' in window.message_details.text()
        assert '27.075 s | frame 4809' in window.message_details.text()
        assert 'Received: ' + text in window.message_details.text()
        assert item.foreground().color().name() == '#d9e6f4'
    finally:
        window.close()
