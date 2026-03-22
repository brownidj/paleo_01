#!/usr/bin/env bash
set -euo pipefail

python3 -m mypy --config-file mypy.ini --explicit-package-bases \
  domain_types.py \
  trip_repository.py \
  trip_crud.py \
  location_geology.py \
  finds_collection_events.py \
  migrations_schema.py \
  repository_base.py \
  repository_trip_user.py \
  repository_location.py \
  repository_finds.py \
  repository_geology_schema.py \
  repository_geology_data.py \
  repository_migrations.py \
  ui/planning_phase_window.py \
  ui/planning_tabs_controller.py \
  ui/trip_navigation_coordinator.py \
  ui/trip_dialog_controller.py
