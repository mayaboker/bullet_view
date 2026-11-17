"""Bullet View application entry point."""
import argparse
import sys

from PySide6 import QtWidgets

from .presenter import Presenter
from .view import MainWindow
from .desktop import add_launcher_arguments, handle_launcher_arguments, configure_application


DEFAULT_ENDPOINT = 'udpin:127.0.0.1:14550'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Bullet View MAVLink telemetry viewer')
    add_launcher_arguments(parser)
    parser.add_argument('--mavlink-endpoint', default=DEFAULT_ENDPOINT,
                        help='App MAVLink UDP listener (udpin:HOST:PORT)')
    args = parser.parse_args(argv)
    try:
        setup = handle_launcher_arguments(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if setup is not None:
        return setup
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    configure_application(application)
    presenter = Presenter(args.mavlink_endpoint, image_mode='remote')
    window = MainWindow(presenter)
    window.show()
    presenter.start()
    return application.exec()


if __name__ == '__main__':
    raise SystemExit(main())
