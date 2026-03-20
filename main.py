from ui.planning_phase_window import PlanningPhaseWindow


def main() -> None:
    """Main entry point for the planning-phase Trip app."""
    app = PlanningPhaseWindow("paleo_trips_01.db")
    app.mainloop()


if __name__ == "__main__":
    main()
