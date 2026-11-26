"""Bullet View application entry point."""
import argparse
import logging
import sys

from PySide6 import QtCore, QtWidgets

from .presenter import Presenter
from .view import MainWindow
from .desktop import add_launcher_arguments, handle_launcher_arguments, configure_application
from bullet_simulation_protocol import validate_endpoint
from bullet_simulation_protocol.state import DEFAULT_CONTROL_ENDPOINT, DEFAULT_STATE_ENDPOINT


DEFAULT_ENDPOINT = 'udpin:127.0.0.1:14550'
WINDOW_MARGIN_PX = 20


def place_on_monitor(window, application, name, half=None):
    if half not in (None, 'top', 'bottom'):
        raise ValueError(f'Invalid monitor half: {half}')
    if not name:
        return
    screen = next((screen for screen in application.screens() if screen.name() == name), None)
    if screen is None:
        screen = application.primaryScreen()
        logging.warning('Monitor %s unavailable; using primary monitor %s',
                        name, screen.name() if screen else '(none)')
    if screen is None:
        return
    geometry = QtCore.QRect(screen.availableGeometry())
    if half is not None:
        top_height = geometry.height() // 2
        if half == 'bottom':
            geometry.setTop(geometry.top() + top_height)
        else:
            geometry.setHeight(top_height)
    width = min(window.width(), max(1, geometry.width() - 2 * WINDOW_MARGIN_PX))
    height = min(window.height(), max(1, geometry.height() - 2 * WINDOW_MARGIN_PX))
    window.resize(width, height)
    window.move(geometry.x() + WINDOW_MARGIN_PX, geometry.y() + WINDOW_MARGIN_PX)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Bullet View MAVLink telemetry viewer')
    add_launcher_arguments(parser)
    parser.add_argument('--mavlink-endpoint', default=DEFAULT_ENDPOINT,
                        help='App MAVLink UDP listener (udpin:HOST:PORT)')
    parser.add_argument('--image-endpoint', help='Local renderer image ZMQ endpoint (tcp://HOST:PORT)')
    parser.add_argument('--simulation-control-endpoint', default=DEFAULT_CONTROL_ENDPOINT,
                        help='Launcher simulation command endpoint')
    parser.add_argument('--simulation-state-endpoint', default=DEFAULT_STATE_ENDPOINT,
                        help='Launcher simulation state publisher endpoint')
    parser.add_argument('--app-launch-script',
                        help='Path to run_app_after_sitl.sh for the Reset App button')
    parser.add_argument('--app-mission',
                        help='Mission argument for the app launch script (hover-land or target-hit)')
    parser.add_argument('--monitor', help='Qt screen name for the Bullet View window')
    parser.add_argument('--monitor-half', choices=('top', 'bottom'),
                        help='Use the top or bottom half of --monitor')
    args = parser.parse_args(argv)
    if args.monitor_half and not args.monitor:
        parser.error('--monitor-half requires --monitor')
    if bool(args.app_launch_script) != bool(args.app_mission):
        parser.error('--app-launch-script and --app-mission must be used together')
    for endpoint in (args.simulation_control_endpoint, args.simulation_state_endpoint):
        try:
            validate_endpoint(endpoint)
        except ValueError as error:
            parser.error(str(error))
    try:
        setup = handle_launcher_arguments(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if setup is not None:
        return setup
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    configure_application(application)
    presenter = Presenter(args.mavlink_endpoint, image_endpoint=args.image_endpoint,
                          simulation_control_endpoint=args.simulation_control_endpoint,
                          simulation_state_endpoint=args.simulation_state_endpoint,
                          app_launch_script=args.app_launch_script,
                          app_mission=args.app_mission)
    window = MainWindow(presenter)
    place_on_monitor(window, application, args.monitor, args.monitor_half)
    window.show()
    presenter.start()
    return application.exec()


if __name__ == '__main__':
    raise SystemExit(main())
