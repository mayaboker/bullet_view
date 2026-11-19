from PySide6 import QtCore, QtWidgets

from bullet_view.main import place_on_monitor


class Screen:
    def __init__(self, name, geometry):
        self._name = name
        self._geometry = geometry

    def name(self):
        return self._name

    def availableGeometry(self):
        return self._geometry


class Application:
    def __init__(self):
        self.primary = Screen('primary', QtCore.QRect(0, 0, 1920, 1080))
        self.secondary = Screen('HDMI-1-0', QtCore.QRect(3000, 0, 1080, 1920))

    def screens(self):
        return [self.primary, self.secondary]

    def primaryScreen(self):
        return self.primary


def test_named_monitor_places_window_within_available_area(qt_application):
    window = QtWidgets.QWidget()
    window.resize(1360, 900)
    place_on_monitor(window, Application(), 'HDMI-1-0')
    assert window.geometry() == QtCore.QRect(3020, 20, 1040, 900)


def test_missing_monitor_uses_primary(qt_application):
    window = QtWidgets.QWidget()
    window.resize(1360, 900)
    place_on_monitor(window, Application(), 'missing')
    assert window.geometry() == QtCore.QRect(20, 20, 1360, 900)


def test_bottom_half_uses_lower_region(qt_application):
    window = QtWidgets.QWidget()
    window.resize(1360, 900)
    application = Application()
    application.secondary = Screen('DP-1-0', QtCore.QRect(1920, 0, 1080, 1920))
    place_on_monitor(window, application, 'DP-1-0', 'bottom')
    assert window.geometry() == QtCore.QRect(1940, 980, 1040, 900)
