#!/usr/bin/env bash
set -euo pipefail

python3 -m mypy --config-file config/mypy.ini --explicit-package-bases \
  repository/domain_types.py \
  repository/trip_repository.py \
  repository/trip_crud.py \
  repository/location_geology.py \
  repository/finds_collection_events.py \
  repository/migrations_schema.py \
  repository/repository_base.py \
  repository/repository_trip_user.py \
  repository/repository_location.py \
  repository/repository_finds.py \
  repository/repository_geology_schema.py \
  repository/repository_geology_data.py \
  repository/repository_migrations.py \
  ui/planning_phase_window.py \
  ui/planning_tabs_controller.py \
  ui/trip_navigation_coordinator.py \
  ui/trip_dialog_controller.py
