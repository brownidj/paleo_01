from repository_base import DEFAULT_TRIP_FIELDS, LOCATION_FIELDS, RepositoryBase
from finds_collection_events import FindsCollectionEventsMixin
from location_geology import LocationGeologyMixin
from migrations_schema import MigrationsSchemaMixin
from trip_crud import TripCrudMixin


class TripRepository(
    RepositoryBase,
    MigrationsSchemaMixin,
    TripCrudMixin,
    LocationGeologyMixin,
    FindsCollectionEventsMixin,
):
    """Repository façade composed from focused mixins."""


__all__ = ["TripRepository", "DEFAULT_TRIP_FIELDS", "LOCATION_FIELDS"]
