class TripSummary {
  const TripSummary({
    required this.id,
    required this.tripName,
    this.startDate,
    this.endDate,
    this.location,
    this.notes,
    this.team,
  });

  final int id;
  final String tripName;
  final String? startDate;
  final String? endDate;
  final String? location;
  final String? notes;
  final String? team;

  factory TripSummary.fromJson(Map<String, dynamic> json) {
    return TripSummary(
      id: int.tryParse((json['id'] ?? '').toString()) ?? 0,
      tripName: (json['trip_name'] ?? '').toString(),
      startDate: _asNullable(json['start_date']),
      endDate: _asNullable(json['end_date']),
      location: _asNullable(json['location']),
      notes: _asNullable(json['notes']),
      team: _asNullable(json['team']),
    );
  }
}

class TeamMemberSummary {
  const TeamMemberSummary({
    required this.id,
    required this.name,
  });

  final int id;
  final String name;

  factory TeamMemberSummary.fromJson(Map<String, dynamic> json) {
    return TeamMemberSummary(
      id: int.tryParse((json['id'] ?? '').toString()) ?? 0,
      name: (json['name'] ?? '').toString(),
    );
  }
}

class TripLocationSummary {
  const TripLocationSummary({
    required this.id,
    required this.name,
  });

  final int id;
  final String name;

  factory TripLocationSummary.fromJson(Map<String, dynamic> json) {
    return TripLocationSummary(
      id: int.tryParse((json['id'] ?? '').toString()) ?? 0,
      name: (json['name'] ?? '').toString(),
    );
  }
}

class TripCollectionEventSummary {
  const TripCollectionEventSummary({
    required this.id,
    required this.collectionName,
    this.eventYear,
  });

  final int id;
  final String collectionName;
  final int? eventYear;

  factory TripCollectionEventSummary.fromJson(Map<String, dynamic> json) {
    return TripCollectionEventSummary(
      id: int.tryParse((json['id'] ?? '').toString()) ?? 0,
      collectionName: (json['collection_name'] ?? '').toString(),
      eventYear: int.tryParse((json['event_year'] ?? '').toString()),
    );
  }
}

class TripDetail {
  const TripDetail({
    required this.id,
    required this.tripName,
    required this.canViewDetails,
    this.startDate,
    this.endDate,
    this.location,
    this.notes,
    this.team,
    this.findCount,
    this.teamMembers = const <TeamMemberSummary>[],
    this.locations = const <TripLocationSummary>[],
    this.collectionEvents = const <TripCollectionEventSummary>[],
  });

  final int id;
  final String tripName;
  final bool canViewDetails;
  final String? startDate;
  final String? endDate;
  final String? location;
  final String? notes;
  final String? team;
  final int? findCount;
  final List<TeamMemberSummary> teamMembers;
  final List<TripLocationSummary> locations;
  final List<TripCollectionEventSummary> collectionEvents;

  factory TripDetail.fromJson(Map<String, dynamic> json) {
    return TripDetail(
      id: int.tryParse((json['id'] ?? '').toString()) ?? 0,
      tripName: (json['trip_name'] ?? '').toString(),
      canViewDetails: (json['can_view_details'] ?? false) == true,
      startDate: _asNullable(json['start_date']),
      endDate: _asNullable(json['end_date']),
      location: _asNullable(json['location']),
      notes: _asNullable(json['notes']),
      team: _asNullable(json['team']),
      findCount: int.tryParse((json['find_count'] ?? '').toString()),
      teamMembers: ((json['team_members'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map<String, dynamic>>()
          .map(TeamMemberSummary.fromJson)
          .toList()),
      locations: ((json['locations'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map<String, dynamic>>()
          .map(TripLocationSummary.fromJson)
          .toList()),
      collectionEvents: ((json['collection_events'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map<String, dynamic>>()
          .map(TripCollectionEventSummary.fromJson)
          .toList()),
    );
  }
}

String? _asNullable(dynamic value) {
  final text = (value ?? '').toString().trim();
  return text.isEmpty ? null : text;
}
