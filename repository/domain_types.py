from typing import TypedDict


class TripPayload(TypedDict, total=False):
    id: int
    trip_name: str
    start_date: str | None
    end_date: str | None
    team: str | None
    location: str | None
    notes: str | None


class TripRecord(TripPayload, total=False):
    pass


TripPayloadMap = dict[str, str | None]


class TeamMemberRecord(TypedDict, total=False):
    id: int
    name: str
    phone_number: str
    institution: str | None
    role: str | None
    recruitment_date: str | None
    retirement_date: str | None
    active: int


# Backward compatibility alias.
UserRecord = TeamMemberRecord


class CollectionEventPayload(TypedDict):
    collection_name: str
    collection_subset: str | None


class LocationPayload(TypedDict, total=False):
    name: str | None
    latitude: str | None
    longitude: str | None
    altitude_value: str | None
    altitude_unit: str | None
    country_code: str | None
    state: str | None
    lga: str | None
    basin: str | None
    proterozoic_province: str | None
    orogen: str | None
    geogscale: str | None
    geography_comments: str | None
    geology_id: int | None
    collection_events: list[CollectionEventPayload]


class LocationRecord(LocationPayload, total=False):
    id: int
    collection_name: str | None
    collection_subset: str | None


LocationPayloadMap = dict[str, str | int | None | list[CollectionEventPayload]]


class FindRecord(TypedDict, total=False):
    id: int
    location_id: int | None
    collection_event_id: int | None
    team_member_id: int | None
    team_member_name: str | None
    source_system: str | None
    source_occurrence_no: str | None
    accepted_name: str | None
    identified_name: str | None
    identified_rank: str | None
    accepted_rank: str | None
    difference: str | None
    identified_no: str | None
    accepted_no: str | None
    phylum: str | None
    class_name: str | None
    taxon_order: str | None
    family: str | None
    genus: str | None
    abund_value: str | None
    abund_unit: str | None
    reference_no: str | None
    taxonomy_comments: str | None
    occurrence_comments: str | None
    research_group: str | None
    notes: str | None
    collection_year_latest_estimate: int | None
    find_date: str | None
    find_time: str | None
    latitude: str | None
    longitude: str | None
    created_at: str | None
    updated_at: str | None
    trip_name: str | None
    collection_name: str | None
    location_name: str | None
    collection_subset: str | None


class CollectionEventRecord(TypedDict, total=False):
    id: int
    trip_id: int | None
    event_year: int | None
    collection_name: str | None
    collection_subset: str | None
    boundary_geojson: str | None
    location_name: str | None
    find_count: int


class LithologyRow(TypedDict, total=False):
    slot: int
    lithology: str | None
    lithification: str | None
    minor_lithology: str | None
    lithology_adjectives: str | None
    fossils_from: str | None


class GeologyRecord(TypedDict, total=False):
    geology_id: int
    location_id: int
    location_name: str | None
    source_reference_no: str | None
    early_interval: str | None
    late_interval: str | None
    max_ma: float | None
    min_ma: float | None
    environment: str | None
    geogscale: str | None
    geology_comments: str | None
    formation: str | None
    stratigraphy_group: str | None
    member: str | None
    stratscale: str | None
    stratigraphy_comments: str | None
    geoplate: str | None
    paleomodel: str | None
    paleolat: float | None
    paleolng: float | None
    state: str | None
    country_code: str | None
    lithology_rows: list[LithologyRow]
    lithology_summary: str


class GeologyUpdatePayload(TypedDict, total=False):
    source_reference_no: str | None
    early_interval: str | None
    late_interval: str | None
    max_ma: float | None
    min_ma: float | None
    environment: str | None
    geogscale: str | None
    geology_comments: str | None
    formation: str | None
    stratigraphy_group: str | None
    member: str | None
    stratscale: str | None
    stratigraphy_comments: str | None
    geoplate: str | None
    paleomodel: str | None
    paleolat: float | None
    paleolng: float | None
    lithology_rows: list[LithologyRow]


GeologyUpdatePayloadMap = dict[str, object]
