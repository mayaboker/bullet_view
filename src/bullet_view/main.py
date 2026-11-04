"""Bullet View application entry point."""
import argparse
import sys

from PySide6 import QtWidgets

from .presenter import Presenter
from .view import MainWindow
from .desktop import add_launcher_arguments, handle_launcher_arguments, configure_application


DEFAULT_ENDPOINT = 'udpin:0.0.0.0:14550'
DEFAULT_IMAGE_ENDPOINT = 'tcp://127.0.0.1:5556'
DEFAULT_IMAGE_TOPIC = 'camera/front/image'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Bullet View MAVLink telemetry viewer')
    add_launcher_arguments(parser)
    parser.add_argument('--mavlink-endpoint', default=DEFAULT_ENDPOINT,
                        help='pymavlink input connection string')
    parser.add_argument('--mavlink-control-endpoint', default='udpout:127.0.0.1:14551',
                        help='pymavlink control output for parameters and profile reload')
    parser.add_argument('--image-endpoint', default=DEFAULT_IMAGE_ENDPOINT,
                        help='local ZMQ image descriptor endpoint')
    parser.add_argument('--image-topic', default=DEFAULT_IMAGE_TOPIC,
                        help='local SHM image topic')
    args = parser.parse_args(argv)
    try:
        setup = handle_launcher_arguments(args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if setup is not None:
        return setup
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    configure_application(application)
    presenter = Presenter(args.mavlink_endpoint, control_endpoint=args.mavlink_control_endpoint,
                          image_endpoint=args.image_endpoint, image_topic=args.image_topic,
                          image_mode='local')
    window = MainWindow(presenter)
    window.show()
    presenter.start()
    return application.exec()


if __name__ == '__main__':
    raise SystemExit(main())
