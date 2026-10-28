"""
main.py
Application entry point for Hand Gesture Controller.

Phase 7: Final QA, Bug Fixes, Regression Testing & College Viva Edition.
Run with:
    python main.py
or
    python main.py --camera-index 0
"""

import argparse
import logging
import sys
import tkinter as tk

from app.camera import CameraService
from app.config import APP_SUBTITLE, APP_TITLE, DEFAULT_CAMERA_INDEX
from app.ui import AppUI


def setup_logging(debug: bool = False) -> None:
    """Configure console logging format."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_arguments() -> argparse.Namespace:
    """Parse optional command-line arguments."""
    parser = argparse.ArgumentParser(
        description=f"{APP_TITLE} - {APP_SUBTITLE}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
        help="Device index of the webcam to use (0 is default on MacBook)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def main() -> int:
    """Initialize application components and start Tkinter event loop."""
    args = parse_arguments()
    setup_logging(debug=args.debug)

    logger = logging.getLogger("main")
    logger.info("Initializing %s (%s)...", APP_TITLE, APP_SUBTITLE)

    # Initialize camera service (does not open camera device until Start is pressed)
    camera_service = CameraService(camera_index=args.camera_index)

    # Initialize Tkinter root window
    root = tk.Tk()

    # Initialize UI
    app = AppUI(root=root, camera_service=camera_service)

    try:
        logger.info("Entering Tkinter main loop. Application ready.")
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user (KeyboardInterrupt).")
    finally:
        logger.info("Cleaning up resources...")
        camera_service.close()

    logger.info("Application exited successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
