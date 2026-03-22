from repository.finds_collection_events import FindsCollectionEventsMixin
from repository.location_geology import LocationGeologyMixin
from repository.migrations_schema import MigrationsSchemaMixin
from repository.repository_base import DEFAULT_TRIP_FIELDS, LOCATION_FIELDS, RepositoryBase
from repository.trip_crud import TripCrudMixin


class TripRepository(
    RepositoryBase,
    MigrationsSchemaMixin,
    TripCrudMixin,
    LocationGeologyMixin,
    FindsCollectionEventsMixin,
):
    """Repository façade composed from focused mixins."""


__all__ = ["TripRepository", "DEFAULT_TRIP_FIELDS", "LOCATION_FIELDS"]
