from database_manager import DatabaseManager
from ui.ui_services import UIService
from ui.main_window import MainWindow


def build_main_window() -> MainWindow:
    """Create and wire the application root objects."""
    db = DatabaseManager("data/paleo_field.db")
    ui_service = UIService(db)
    return MainWindow(ui_service)
