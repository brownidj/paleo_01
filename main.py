from app_composition import build_main_window
from logger import logger
import sys

def main():
    """Main entry point for the Paleo_01 field recording system."""
    # Enable debug mode if --debug flag is present
    if "--debug" in sys.argv:
        logger.set_debug(True)
        logger.info("Debug mode enabled")

    logger.info("Starting Paleo_01 Field Recording System")
    app = build_main_window()
    app.mainloop()

if __name__ == '__main__':
    main()
