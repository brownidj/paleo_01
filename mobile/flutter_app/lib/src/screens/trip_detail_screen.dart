import 'dart:convert';

import 'package:flutter/material.dart';

import '../models/trip_models.dart';

typedef CreateFindFn =
    Future<void> Function({
      required int collectionEventId,
      required int teamMemberId,
      required String findDate,
      required String findTime,
      String? latitude,
      String? longitude,
    });

class TripDetailScreen extends StatefulWidget {
  const TripDetailScreen({
    super.key,
    required this.trip,
    required this.defaultTeamMemberId,
    required this.onCreateFind,
  });

  final TripDetail trip;
  final int defaultTeamMemberId;
  final CreateFindFn onCreateFind;

  @override
  State<TripDetailScreen> createState() => _TripDetailScreenState();
}

class _TripDetailScreenState extends State<TripDetailScreen> {
  int? _activeCollectionEventId;
  bool _savingFind = false;
  bool _teamExpanded = false;

  @override
  void initState() {
    super.initState();
    _activeCollectionEventId = widget.trip.collectionEvents.isNotEmpty
        ? widget.trip.collectionEvents.first.id
        : null;
  }

  @override
  Widget build(BuildContext context) {
    final trip = widget.trip;
    final start = _display(trip.startDate);
    final locationText = _display(trip.location);
    final sortedTeamMembers = _sortedUniqueTeamMembers();

    return Scaffold(
      appBar: AppBar(title: Text(trip.tripName)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _section(
            context,
            title: 'Trip',
            headerValue: 'Starts: $start',
            children: const [],
            titleBodySpacing: 0,
            contentVerticalPadding: 0,
          ),
          const SizedBox(height: 12),
          if (!trip.canViewDetails)
            Card(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              child: const Padding(
                padding: EdgeInsets.all(12),
                child: Text(
                  'You are not assigned to this trip’s team. Contact admin for detail access.',
                ),
              ),
            ),
          if (trip.canViewDetails) ...[
            _section(
              context,
              title: 'Collection Events',
              children: _collectionEventRows(trip.collectionEvents),
              titleBodySpacing: 0,
              contentVerticalPadding: 4,
            ),
            const SizedBox(height: 12),
            _section(
              context,
              title: 'Finds',
              headerValue: '${trip.findCount ?? 0}',
              headerAction: IconButton(
                icon: const Icon(Icons.add),
                tooltip: 'New Find',
                onPressed: (_savingFind || _activeCollectionEventId == null)
                    ? null
                    : _openNewFindDialog,
              ),
              children: const [],
              titleBodySpacing: 0,
              contentVerticalPadding: 0,
            ),
            const SizedBox(height: 12),
            _section(
              context,
              title: 'Team',
              headerAction: IconButton(
                icon: Icon(
                  _teamExpanded ? Icons.expand_more : Icons.chevron_right,
                ),
                tooltip: _teamExpanded ? 'Hide team' : 'Show team',
                onPressed: () {
                  setState(() {
                    _teamExpanded = !_teamExpanded;
                  });
                },
              ),
              children: sortedTeamMembers
                  .map((name) => Text('• $name'))
                  .toList(growable: false),
              collapsed: !_teamExpanded,
            ),
            const SizedBox(height: 12),
            _section(
              context,
              title: 'Location',
              headerValue: locationText,
              children: [...trip.locations.map((row) => Text('• ${row.name}'))],
              titleBodySpacing: trip.locations.isEmpty ? 0 : 8,
              contentVerticalPadding: trip.locations.isEmpty ? 0 : 12,
            ),
          ],
        ],
      ),
    );
  }

  List<Widget> _collectionEventRows(List<TripCollectionEventSummary> rows) {
    if (rows.isEmpty) {
      return const [Text('-')];
    }
    return [
      RadioGroup<int>(
        groupValue: _activeCollectionEventId,
        onChanged: (value) {
          setState(() {
            _activeCollectionEventId = value;
          });
        },
        child: Column(
          children: rows
              .map(
                (row) => InkWell(
                  onTap: () {
                    setState(() {
                      _activeCollectionEventId = row.id;
                    });
                  },
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 1),
                    child: Row(
                      children: [
                        Radio<int>(
                          value: row.id,
                          visualDensity: const VisualDensity(
                            horizontal: VisualDensity.minimumDensity,
                            vertical: VisualDensity.minimumDensity,
                          ),
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                        ),
                        const SizedBox(width: 2),
                        Expanded(
                          child: Text(
                            '${row.collectionName}${row.eventYear != null ? ' (${row.eventYear})' : ''}',
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              )
              .toList(growable: false),
        ),
      ),
    ];
  }

  Future<void> _openNewFindDialog() async {
    final eventId = _activeCollectionEventId;
    if (eventId == null) {
      return;
    }
    final teamMemberName = _currentTeamMemberName();
    final seededLatLon = _seedLatLonFromBoundary(eventId);
    final fallbackLatLon = _fallbackFakeDeviceLatLon();
    const photoRequiredTooltip =
        'At least 1 photo must be included before this Find can be saved';
    const photoCount = 0;
    Map<String, String?> observationsDraft = <String, String?>{
      'provisional_identification': 'Unknown',
      'abund_value': 'Single',
      'notes': '',
    };
    final now = DateTime.now();
    final dateController = TextEditingController(text: _formatDate(now));
    final timeController = TextEditingController(text: _formatTime(now));
    final latitudeController = TextEditingController(
      text: seededLatLon.$1 ?? fallbackLatLon.$1,
    );
    final longitudeController = TextEditingController(
      text: seededLatLon.$2 ?? fallbackLatLon.$2,
    );

    final result = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: Row(
              children: [
                const Expanded(child: Text('New Find')),
                IconButton(
                  onPressed: () => Navigator.of(dialogContext).pop(false),
                  tooltip: 'Cancel',
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            content: SizedBox(
              width: 420,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text('CE: $eventId')),
                      Expanded(
                        child: Text(teamMemberName, textAlign: TextAlign.right),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: dateController,
                    decoration: InputDecoration(
                      labelText: 'Date',
                      suffixIcon: IconButton(
                        icon: const Icon(Icons.calendar_today),
                        onPressed: () async {
                          final picked = await showDatePicker(
                            context: context,
                            initialDate: _parseDate(dateController.text) ?? now,
                            firstDate: DateTime(1900),
                            lastDate: DateTime(2100),
                          );
                          if (picked == null) {
                            return;
                          }
                          setDialogState(() {
                            dateController.text = _formatDate(picked);
                          });
                        },
                      ),
                    ),
                  ),
                  TextField(
                    controller: timeController,
                    decoration: InputDecoration(
                      labelText: 'Time',
                      suffixIcon: IconButton(
                        icon: const Icon(Icons.access_time),
                        onPressed: () async {
                          final parsed = _parseTime(timeController.text);
                          final picked = await showTimePicker(
                            context: context,
                            initialTime: parsed ?? TimeOfDay.fromDateTime(now),
                          );
                          if (picked == null) {
                            return;
                          }
                          setDialogState(() {
                            timeController.text = _formatTimeOfDay(picked);
                          });
                        },
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: const [
                      Expanded(child: Text('Latitude')),
                      SizedBox(width: 12),
                      Expanded(child: Text('Longitude')),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: latitudeController,
                          keyboardType: const TextInputType.numberWithOptions(
                            signed: true,
                            decimal: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextField(
                          controller: longitudeController,
                          keyboardType: const TextInputType.numberWithOptions(
                            signed: true,
                            decimal: true,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            actions: [
              SizedBox(
                width: double.infinity,
                child: Row(
                  children: [
                    Wrap(
                      spacing: 8,
                      children: [
                        ActionChip(
                          onPressed: () {},
                          tooltip: photoRequiredTooltip,
                          label: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                Icons.camera_alt_outlined,
                                size: 18,
                                color: Theme.of(context).colorScheme.onPrimary,
                              ),
                              const SizedBox(width: 4),
                              Text(
                                '$photoCount',
                                style: TextStyle(
                                  color: Theme.of(
                                    context,
                                  ).colorScheme.onPrimary,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                          labelPadding: EdgeInsets.zero,
                          padding: const EdgeInsets.symmetric(horizontal: 5),
                          backgroundColor: Theme.of(
                            context,
                          ).colorScheme.primary,
                          side: BorderSide.none,
                          visualDensity: VisualDensity.compact,
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                        ),
                        ActionChip(
                          onPressed: photoCount <= 0
                              ? null
                              : () async {
                                  final updated =
                                      await _openFindFieldObservationsDialog(
                                        context,
                                        initialValues: observationsDraft,
                                        photoCount: photoCount,
                                      );
                                  if (updated != null) {
                                    observationsDraft = updated;
                                  }
                                },
                          tooltip: 'Observations',
                          label: Icon(
                            Icons.visibility_outlined,
                            size: 18,
                            color: Theme.of(context).colorScheme.onPrimary,
                          ),
                          labelPadding: EdgeInsets.zero,
                          padding: const EdgeInsets.symmetric(horizontal: 5),
                          backgroundColor: Theme.of(
                            context,
                          ).colorScheme.primary,
                          disabledColor: Theme.of(
                            context,
                          ).colorScheme.surfaceContainerHighest,
                          side: BorderSide.none,
                          visualDensity: VisualDensity.compact,
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                        ),
                      ],
                    ),
                    const Spacer(),
                    Tooltip(
                      message: photoCount == 0 ? photoRequiredTooltip : '',
                      triggerMode: TooltipTriggerMode.longPress,
                      child: const FilledButton(
                        onPressed: null,
                        child: Text('Save'),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );

    if (result != true) {
      dateController.dispose();
      timeController.dispose();
      latitudeController.dispose();
      longitudeController.dispose();
      return;
    }
    if (widget.defaultTeamMemberId <= 0) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Cannot create find: no team member is linked to this account.',
            ),
          ),
        );
      }
      dateController.dispose();
      timeController.dispose();
      latitudeController.dispose();
      longitudeController.dispose();
      return;
    }

    setState(() {
      _savingFind = true;
    });
    try {
      await widget.onCreateFind(
        collectionEventId: eventId,
        teamMemberId: widget.defaultTeamMemberId,
        findDate: dateController.text.trim(),
        findTime: timeController.text.trim(),
        latitude: _nullableText(latitudeController.text),
        longitude: _nullableText(longitudeController.text),
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Find created.')));
    } catch (exc) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Create find failed: $exc')));
    } finally {
      dateController.dispose();
      timeController.dispose();
      latitudeController.dispose();
      longitudeController.dispose();
      if (mounted) {
        setState(() {
          _savingFind = false;
        });
      }
    }
  }

  Widget _section(
    BuildContext context, {
    required String title,
    required List<Widget> children,
    Widget? headerAction,
    String? headerValue,
    bool collapsed = false,
    double titleBodySpacing = 8,
    double contentVerticalPadding = 12,
  }) {
    return Card(
      child: Padding(
        padding: EdgeInsets.fromLTRB(12, 12, 12, contentVerticalPadding),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Row(
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      if ((headerValue ?? '').trim().isNotEmpty) ...[
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            headerValue!,
                            style: Theme.of(context).textTheme.bodyMedium,
                            textAlign: TextAlign.right,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                ?headerAction,
              ],
            ),
            SizedBox(height: titleBodySpacing),
            if (!collapsed) ...children,
          ],
        ),
      ),
    );
  }

  String _display(String? value) =>
      (value ?? '').trim().isEmpty ? '-' : value!.trim();

  String? _nullableText(String value) {
    final normalized = value.trim();
    if (normalized.isEmpty) {
      return null;
    }
    return normalized;
  }

  String _formatDate(DateTime value) {
    return '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
  }

  String _formatTime(DateTime value) {
    return '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
  }

  String _formatTimeOfDay(TimeOfDay value) {
    return '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
  }

  DateTime? _parseDate(String value) {
    final parts = value.trim().split('-');
    if (parts.length != 3) {
      return null;
    }
    final year = int.tryParse(parts[0]);
    final month = int.tryParse(parts[1]);
    final day = int.tryParse(parts[2]);
    if (year == null || month == null || day == null) {
      return null;
    }
    if (month < 1 || month > 12 || day < 1 || day > 31) {
      return null;
    }
    return DateTime(year, month, day);
  }

  TimeOfDay? _parseTime(String value) {
    final parts = value.trim().split(':');
    if (parts.length != 2) {
      return null;
    }
    final hour = int.tryParse(parts[0]);
    final minute = int.tryParse(parts[1]);
    if (hour == null || minute == null) {
      return null;
    }
    if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
      return null;
    }
    return TimeOfDay(hour: hour, minute: minute);
  }

  List<String> _sortedUniqueTeamMembers() {
    final fromRows = widget.trip.teamMembers
        .map((row) => row.name.trim())
        .where((name) => name.isNotEmpty)
        .toList(growable: false);
    final source = fromRows.isNotEmpty
        ? fromRows
        : (widget.trip.team ?? '')
              .split(';')
              .map((name) => name.trim())
              .where((name) => name.isNotEmpty)
              .toList(growable: false);
    final deduped = source.toSet().toList(growable: false);
    deduped.sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase()));
    return deduped;
  }

  String _currentTeamMemberName() {
    final memberId = widget.defaultTeamMemberId;
    if (memberId <= 0) {
      return 'Unassigned';
    }
    for (final row in widget.trip.teamMembers) {
      if (row.id == memberId) {
        final name = row.name.trim();
        if (name.isNotEmpty) {
          return name;
        }
      }
    }
    return '#$memberId';
  }

  (String?, String?) _seedLatLonFromBoundary(int collectionEventId) {
    TripCollectionEventSummary? activeEvent;
    for (final row in widget.trip.collectionEvents) {
      if (row.id == collectionEventId) {
        activeEvent = row;
        break;
      }
    }
    final raw = (activeEvent?.boundaryGeojson ?? '').trim();
    if (raw.isEmpty) {
      return (null, null);
    }
    try {
      final decoded = jsonDecode(raw);
      final points = _extractLonLatPoints(decoded);
      if (points.isEmpty) {
        return (null, null);
      }
      final uniquePoints = _dropDuplicateClosingPoint(points);
      if (uniquePoints.isEmpty) {
        return (null, null);
      }
      double sumLon = 0;
      double sumLat = 0;
      for (final point in uniquePoints) {
        sumLon += point.$1;
        sumLat += point.$2;
      }
      final lon = sumLon / uniquePoints.length;
      final lat = sumLat / uniquePoints.length;
      return (lat.toStringAsFixed(6), lon.toStringAsFixed(6));
    } catch (_) {
      return (null, null);
    }
  }

  (String, String) _fallbackFakeDeviceLatLon() {
    // Placeholder until real GPS capture is wired to the device sensors.
    return ('-19.258963', '146.816948');
  }

  Future<Map<String, String?>?> _openFindFieldObservationsDialog(
    BuildContext context, {
    required Map<String, String?> initialValues,
    required int photoCount,
  }) async {
    final provisionalController = TextEditingController(
      text: (initialValues['provisional_identification'] ?? 'Unknown').trim(),
    );
    final notesController = TextEditingController(
      text: (initialValues['notes'] ?? '').trim(),
    );
    const abundanceOptions = <String>['Single', 'Few', 'Medium', 'Many'];
    String selectedAbundance = (initialValues['abund_value'] ?? '').trim();
    if (!abundanceOptions.contains(selectedAbundance)) {
      selectedAbundance = abundanceOptions.first;
    }
    Map<String, String?>? output;
    try {
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
          builder: (context, setState) => AlertDialog(
            title: Row(
              children: [
                const Expanded(child: Text('Field Observations')),
                IconButton(
                  onPressed: () => Navigator.of(dialogContext).pop(),
                  tooltip: 'Close',
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            content: SizedBox(
              width: 420,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: provisionalController,
                      decoration: const InputDecoration(
                        labelText: 'Provisional identification',
                      ),
                    ),
                    DropdownButtonFormField<String>(
                      initialValue: selectedAbundance,
                      decoration: const InputDecoration(labelText: 'Abundance'),
                      items: abundanceOptions
                          .map(
                            (value) => DropdownMenuItem<String>(
                              value: value,
                              child: Text(value),
                            ),
                          )
                          .toList(growable: false),
                      onChanged: (value) {
                        if (value == null) {
                          return;
                        }
                        setState(() {
                          selectedAbundance = value;
                        });
                      },
                    ),
                    Tooltip(
                      message:
                          'Eg preservation/taphonomy, confidence qualifiers, substrate/context, uncertainty, etc.',
                      triggerMode: TooltipTriggerMode.longPress,
                      child: TextField(
                        controller: notesController,
                        decoration: const InputDecoration(
                          labelText: 'Notes',
                          hintText: 'Enter any useful observations here.',
                        ),
                        minLines: 4,
                        maxLines: 6,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              SizedBox(
                width: double.infinity,
                child: Row(
                  children: [
                    const Spacer(),
                    ActionChip(
                      onPressed: photoCount <= 0
                          ? null
                          : () {
                              output = <String, String?>{
                                'provisional_identification':
                                    provisionalController.text.trim().isEmpty
                                    ? 'Unknown'
                                    : provisionalController.text.trim(),
                                'abund_value': selectedAbundance,
                                'notes': notesController.text.trim(),
                              };
                              Navigator.of(dialogContext).pop();
                            },
                      label: const Text('Save'),
                      backgroundColor: Theme.of(context).colorScheme.primary,
                      disabledColor: Theme.of(
                        context,
                      ).colorScheme.surfaceContainerHighest,
                      labelStyle: TextStyle(
                        color: photoCount <= 0
                            ? Theme.of(context).colorScheme.onSurfaceVariant
                            : Theme.of(context).colorScheme.onPrimary,
                        fontWeight: FontWeight.w600,
                      ),
                      side: BorderSide.none,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
    } finally {
      provisionalController.dispose();
      notesController.dispose();
    }
    return output;
  }

  List<(double, double)> _extractLonLatPoints(dynamic geojson) {
    dynamic geometry = geojson;
    if (geometry is Map<String, dynamic>) {
      final type = (geometry['type'] ?? '').toString();
      if (type == 'Feature') {
        geometry = geometry['geometry'];
      } else if (type == 'FeatureCollection') {
        final features = geometry['features'];
        if (features is List && features.isNotEmpty) {
          final first = features.first;
          if (first is Map<String, dynamic>) {
            geometry = first['geometry'];
          }
        }
      }
    }
    if (geometry is! Map<String, dynamic>) {
      return const <(double, double)>[];
    }
    final type = (geometry['type'] ?? '').toString();
    final coords = geometry['coordinates'];
    if (coords is! List) {
      return const <(double, double)>[];
    }
    if (type == 'Polygon') {
      return _pointsFromRing(coords.isNotEmpty ? coords.first : null);
    }
    if (type == 'MultiPolygon') {
      if (coords.isEmpty) {
        return const <(double, double)>[];
      }
      final firstPolygon = coords.first;
      if (firstPolygon is! List || firstPolygon.isEmpty) {
        return const <(double, double)>[];
      }
      return _pointsFromRing(firstPolygon.first);
    }
    return const <(double, double)>[];
  }

  List<(double, double)> _pointsFromRing(dynamic ring) {
    if (ring is! List) {
      return const <(double, double)>[];
    }
    final out = <(double, double)>[];
    for (final vertex in ring) {
      if (vertex is! List || vertex.length < 2) {
        continue;
      }
      final lon = _toDouble(vertex[0]);
      final lat = _toDouble(vertex[1]);
      if (lon == null || lat == null) {
        continue;
      }
      out.add((lon, lat));
    }
    return out;
  }

  List<(double, double)> _dropDuplicateClosingPoint(
    List<(double, double)> points,
  ) {
    if (points.length < 2) {
      return points;
    }
    final first = points.first;
    final last = points.last;
    if ((first.$1 - last.$1).abs() < 0.0000001 &&
        (first.$2 - last.$2).abs() < 0.0000001) {
      return points.sublist(0, points.length - 1);
    }
    return points;
  }

  double? _toDouble(dynamic value) {
    if (value is num) {
      return value.toDouble();
    }
    return double.tryParse(value.toString());
  }
}
