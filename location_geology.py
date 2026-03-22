from repository_geology_data import RepositoryGeologyDataMixin
from repository_location import RepositoryLocationMixin


class LocationGeologyMixin(RepositoryLocationMixin, RepositoryGeologyDataMixin):
    """Location CRUD/list and geology read/write operations."""
