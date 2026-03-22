from repository_geology_schema import RepositoryGeologySchemaMixin
from repository_migrations import RepositoryMigrationMixin


class MigrationsSchemaMixin(RepositoryMigrationMixin, RepositoryGeologySchemaMixin):
    """Schema creation and legacy migration helpers."""
