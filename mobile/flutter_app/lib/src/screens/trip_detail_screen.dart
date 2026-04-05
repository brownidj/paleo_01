import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as p;

import '../data/mobile_data_repository.dart';
import '../local_db/app_local_database.dart';
import '../models/trip_models.dart';

typedef CreateFindFn =
    Future<void> Function({
      required int collectionEventId,
      required int teamMemberId,
      required String findDate,
      required String findTime,
      required List<CreateFindPhotoInput> photos,
      String? provisionalIdentification,
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
  bool _findsExpanded = false;
  bool _findsLoading = false;
  bool _teamExpanded = false;
  final AppLocalDatabase _localDb = AppLocalDatabase();
  List<_LocalFindRow> _localFindRows = const <_LocalFindRow>[];

  @override
  void initState() {
    super.initState();
    _activeCollectionEventId = widget.trip.collectionEvents.isNotEmpty
        ? widget.trip.collectionEvents.first.id
        : null;
    _reloadLocalFinds();
  }

  @override
  void dispose() {
    _localDb.close();
    super.dispose();
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
              headerValue: '${_localFindRows.length}',
              titleAction: IconButton(
                icon: Icon(
                  _findsExpanded ? Icons.expand_more : Icons.chevron_right,
                ),
                tooltip: _findsExpanded ? 'Hide finds' : 'Show finds',
                onPressed: () {
                  setState(() {
                    _findsExpanded = !_findsExpanded;
                  });
                },
              ),
              headerAction: IconButton(
                icon: const Icon(Icons.add),
                tooltip: 'New Find',
                onPressed: (_savingFind || _activeCollectionEventId == null)
                    ? null
                    : _openNewFindDialog,
              ),
              children: _buildFindRows(context),
              collapsed: !_findsExpanded,
              titleBodySpacing: 0,
              contentVerticalPadding: _findsExpanded ? 12 : 0,
            ),
            const SizedBox(height: 12),
            _section(
              context,
              title: 'Team',
              titleAction: IconButton(
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
          _reloadLocalFinds();
        },
        child: Column(
          children: rows
              .map(
                (row) => InkWell(
                  onTap: () {
                    setState(() {
                      _activeCollectionEventId = row.id;
                    });
                    _reloadLocalFinds();
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
    var draftPhotos = <_DraftPhoto>[];
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
                const Expanded(child: Text('Add Find')),
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
                          onPressed: () async {
                            final updated = await _openPhotosDialog(
                              context,
                              existing: draftPhotos,
                            );
                            if (updated != null) {
                              setDialogState(() {
                                draftPhotos = updated;
                              });
                            }
                          },
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
                                '${draftPhotos.length}',
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
                          onPressed: draftPhotos.isEmpty
                              ? null
                              : () async {
                                  final updated =
                                      await _openFindFieldObservationsDialog(
                                        context,
                                        initialValues: observationsDraft,
                                        photoCount: draftPhotos.length,
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
                      message: draftPhotos.isEmpty ? photoRequiredTooltip : '',
                      triggerMode: TooltipTriggerMode.longPress,
                      child: FilledButton(
                        onPressed: draftPhotos.isEmpty
                            ? null
                            : () {
                                final date = dateController.text.trim();
                                final time = timeController.text.trim();
                                final latitude = latitudeController.text.trim();
                                final longitude = longitudeController.text
                                    .trim();
                                if (date.isEmpty || time.isEmpty) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text(
                                        'Date and Time are required.',
                                      ),
                                    ),
                                  );
                                  return;
                                }
                                if (latitude.isNotEmpty &&
                                    double.tryParse(latitude) == null) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text(
                                        'Latitude must be a valid number.',
                                      ),
                                    ),
                                  );
                                  return;
                                }
                                if (longitude.isNotEmpty &&
                                    double.tryParse(longitude) == null) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text(
                                        'Longitude must be a valid number.',
                                      ),
                                    ),
                                  );
                                  return;
                                }
                                Navigator.of(dialogContext).pop(true);
                              },
                        child: const Text('Save'),
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
      _disposeControllersNextFrame([
        dateController,
        timeController,
        latitudeController,
        longitudeController,
      ]);
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
      _disposeControllersNextFrame([
        dateController,
        timeController,
        latitudeController,
        longitudeController,
      ]);
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
        photos: draftPhotos
            .map(
              (row) => CreateFindPhotoInput(
                filePath: row.filePath,
                source: row.source,
                capturedAtIso: row.capturedAtIso,
              ),
            )
            .toList(growable: false),
        provisionalIdentification: _nullableText(
          observationsDraft['provisional_identification'] ?? '',
        ),
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
      _disposeControllersNextFrame([
        dateController,
        timeController,
        latitudeController,
        longitudeController,
      ]);
      if (mounted) {
        setState(() {
          _savingFind = false;
        });
        _reloadLocalFinds();
      }
    }
  }

  List<Widget> _buildFindRows(BuildContext context) {
    if (_findsLoading) {
      return const <Widget>[
        Padding(
          padding: EdgeInsets.symmetric(vertical: 8),
          child: Center(child: CircularProgressIndicator()),
        ),
      ];
    }
    if (_localFindRows.isEmpty) {
      return const <Widget>[
        Text('No local finds for this collection event yet.'),
      ];
    }
    return <Widget>[
      ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 220),
        child: Scrollbar(
          thumbVisibility: false,
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: _localFindRows.length,
            separatorBuilder: (context, index) => const Divider(height: 12),
            itemBuilder: (context, index) {
              final row = _localFindRows[index];
              final whenLabel = _formatFindRowDateTime(
                row.findDate,
                row.findTime,
              );
              final provisional =
                  (row.provisionalIdentification ?? '').trim().isEmpty
                  ? 'Unknown'
                  : row.provisionalIdentification!.trim();
              final initials = _teamMemberInitials(row.teamMemberId);
              return InkWell(
                onTap: () => _openEditFindDialog(row),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          '$whenLabel • $provisional • $initials',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        row.syncStatus,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    ];
  }

  Future<void> _openEditFindDialog(_LocalFindRow row) async {
    final dateController = TextEditingController(text: row.findDate);
    final timeController = TextEditingController(text: row.findTime);
    final latitudeController = TextEditingController(text: row.latitude ?? '');
    final longitudeController = TextEditingController(
      text: row.longitude ?? '',
    );
    var observationsDraft = <String, String?>{
      'provisional_identification': row.provisionalIdentification ?? 'Unknown',
      'abund_value': row.abundValue ?? 'Single',
      'notes': row.notes ?? '',
    };
    var photoCount = 0;
    try {
      photoCount = (await _localDb.listFindPhotosByFindLocalId(
        row.localId,
      )).length;
    } catch (_) {
      photoCount = 0;
    }
    if (!mounted) {
      _disposeControllersNextFrame([
        dateController,
        timeController,
        latitudeController,
        longitudeController,
      ]);
      return;
    }
    final now = DateTime.now();
    final edited = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Row(
            children: [
              const Expanded(child: Text('Edit Find')),
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
                Text('CE: ${row.collectionEventId}'),
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
                  ActionChip(
                    onPressed: () async {
                      await _openFindPhotosDialogForRow(row);
                      final refreshed = await _localDb.listFindPhotosByFindLocalId(
                        row.localId,
                      );
                      if (!context.mounted) {
                        return;
                      }
                      setDialogState(() {
                        photoCount = refreshed.length;
                      });
                    },
                    tooltip: 'Photos',
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
                            color: Theme.of(context).colorScheme.onPrimary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                    labelPadding: EdgeInsets.zero,
                    padding: const EdgeInsets.symmetric(horizontal: 5),
                    backgroundColor: Theme.of(context).colorScheme.primary,
                    side: BorderSide.none,
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  const SizedBox(width: 8),
                  ActionChip(
                    onPressed: () async {
                      final updated = await _openFindFieldObservationsDialog(
                        context,
                        title: 'Edit Field Observations',
                        initialValues: observationsDraft,
                        photoCount: photoCount,
                      );
                      if (updated != null) {
                        setDialogState(() {
                          observationsDraft = updated;
                        });
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
                    backgroundColor: Theme.of(context).colorScheme.primary,
                    side: BorderSide.none,
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  const Spacer(),
                  FilledButton(
                    onPressed: () {
                      final date = dateController.text.trim();
                      final time = timeController.text.trim();
                      final latitude = latitudeController.text.trim();
                      final longitude = longitudeController.text.trim();
                      if (date.isEmpty || time.isEmpty) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Date and Time are required.'),
                          ),
                        );
                        return;
                      }
                      if (latitude.isNotEmpty &&
                          double.tryParse(latitude) == null) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Latitude must be a valid number.'),
                          ),
                        );
                        return;
                      }
                      if (longitude.isNotEmpty &&
                          double.tryParse(longitude) == null) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Longitude must be a valid number.'),
                          ),
                        );
                        return;
                      }
                      Navigator.of(dialogContext).pop(true);
                    },
                    child: const Text('Save'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );

    if (edited != true) {
      _disposeControllersNextFrame([
        dateController,
        timeController,
        latitudeController,
        longitudeController,
      ]);
      return;
    }
    final nowIso = DateTime.now().toUtc().toIso8601String();
    final findDate = dateController.text.trim();
    final findTime = timeController.text.trim();
    final latitude = _nullableText(latitudeController.text);
    final longitude = _nullableText(longitudeController.text);
    try {
      await _localDb.updateFindLocalFields(
        localId: row.localId,
        collectionEventId: row.collectionEventId,
        teamMemberId: row.teamMemberId,
        source: row.source,
        acceptedName: row.acceptedName,
        findDate: findDate,
        findTime: findTime,
        provisionalIdentification: _nullableText(
          observationsDraft['provisional_identification'] ?? '',
        ),
        abundValue: _nullableText(observationsDraft['abund_value'] ?? ''),
        notes: _nullableText(observationsDraft['notes'] ?? ''),
        latitude: latitude,
        longitude: longitude,
        updatedAtDevice: nowIso,
      );
      await _localDb.updatePendingCreateQueuePayloadForFind(
        localId: row.localId,
        payloadJson: jsonEncode(<String, Object?>{
          'collection_event_id': row.collectionEventId,
          'team_member_id': row.teamMemberId,
          'source': row.source,
          'accepted_name': row.acceptedName,
          'find_date': findDate,
          'find_time': findTime,
          'latitude': latitude,
          'longitude': longitude,
        }),
        updatedAt: nowIso,
      );
      if (!mounted) {
        return;
      }
      await _reloadLocalFinds();
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Find updated.')));
    } catch (exc) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Update failed: $exc')));
    } finally {
      _disposeControllersNextFrame([
        dateController,
        timeController,
        latitudeController,
        longitudeController,
      ]);
    }
  }

  Future<List<_DraftPhoto>?> _openPhotosDialog(
    BuildContext context, {
    required List<_DraftPhoto> existing,
  }) async {
    var photos = List<_DraftPhoto>.from(existing);
    return showDialog<List<_DraftPhoto>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: Row(
            children: [
              const Expanded(child: Text('Photos')),
              IconButton(
                onPressed: () => Navigator.of(dialogContext).pop(),
                tooltip: 'Close',
                icon: const Icon(Icons.close),
              ),
            ],
          ),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (photos.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 8),
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Text('No photos attached yet.'),
                    ),
                  ),
                if (photos.isNotEmpty)
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxHeight: 150),
                    child: Scrollbar(
                      thumbVisibility: false,
                      child: ListView.separated(
                        itemCount: photos.length,
                        separatorBuilder: (context, index) =>
                            const SizedBox(height: 8),
                        itemBuilder: (context, index) {
                          final row = photos[index];
                          return Row(
                            children: [
                              GestureDetector(
                                onTap: () async {
                                  await _openDraftPhotoViewer(context, row);
                                },
                                child: Stack(
                                  children: [
                                    Container(
                                      width: 64,
                                      height: 64,
                                      decoration: BoxDecoration(
                                        color: Theme.of(
                                          context,
                                        ).colorScheme.surfaceContainerHighest,
                                        borderRadius: BorderRadius.circular(8),
                                        border: Border.all(
                                          color: Theme.of(context).dividerColor,
                                        ),
                                      ),
                                      child: File(row.filePath).existsSync()
                                          ? ClipRRect(
                                              borderRadius:
                                                  BorderRadius.circular(8),
                                              child: Image.file(
                                                File(row.filePath),
                                                fit: BoxFit.cover,
                                              ),
                                            )
                                          : Icon(
                                              Icons.image_outlined,
                                              color: Theme.of(
                                                context,
                                              ).colorScheme.onSurfaceVariant,
                                            ),
                                    ),
                                    Positioned(
                                      right: 2,
                                      top: 2,
                                      child: InkWell(
                                        onTap: () {
                                          setState(() {
                                            photos.removeAt(index);
                                          });
                                        },
                                        child: Container(
                                          decoration: BoxDecoration(
                                            color: Theme.of(
                                              context,
                                            ).colorScheme.surface,
                                            shape: BoxShape.circle,
                                          ),
                                          padding: const EdgeInsets.all(2),
                                          child: const Icon(
                                            Icons.close,
                                            size: 14,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      row.label,
                                      overflow: TextOverflow.ellipsis,
                                      style: Theme.of(
                                        context,
                                      ).textTheme.bodyMedium,
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      '${_formatPhotoSource(row.source)} • ${row.capturedAtIso}',
                                      overflow: TextOverflow.ellipsis,
                                      style: Theme.of(
                                        context,
                                      ).textTheme.bodySmall,
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          );
                        },
                      ),
                    ),
                  ),
              ],
            ),
          ),
          actions: [
            SizedBox(
              width: double.infinity,
              child: Row(
                children: [
                  ActionChip(
                    onPressed: () async {
                      final source = await _choosePhotoSource(dialogContext);
                      if (source == null) {
                        return;
                      }
                      final sequence = photos.length + 1;
                      final picker = ImagePicker();
                      try {
                        final file = await picker.pickImage(
                          source: source,
                          imageQuality: 85,
                          maxWidth: 2200,
                          maxHeight: 2200,
                        );
                        if (file == null) {
                          return;
                        }
                        final now = DateTime.now().toUtc();
                        final persistedDraftPath =
                            await _persistDraftPhotoToLocalStorage(file.path);
                        if (persistedDraftPath.isEmpty) {
                          if (!context.mounted) {
                            return;
                          }
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Unable to store selected photo.'),
                            ),
                          );
                          return;
                        }
                        setState(() {
                          photos.add(
                            _DraftPhoto(
                              id: 'draft-${now.microsecondsSinceEpoch}',
                              label: 'Photo $sequence',
                              capturedAtIso: now.toIso8601String(),
                              filePath: persistedDraftPath,
                              source: source == ImageSource.camera
                                  ? 'camera'
                                  : 'gallery',
                            ),
                          );
                        });
                      } on PlatformException catch (exc) {
                        if (!context.mounted) {
                          return;
                        }
                        final message = source == ImageSource.camera
                            ? 'Camera not available. Choose from gallery.'
                            : 'Unable to load photo.';
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('$message (${exc.message ?? 'plugin error'})')),
                        );
                      } on MissingPluginException {
                        if (!context.mounted) {
                          return;
                        }
                        final message = source == ImageSource.camera
                            ? 'Camera not available. Choose from gallery.'
                            : 'Unable to load photo.';
                        ScaffoldMessenger.of(
                          context,
                        ).showSnackBar(SnackBar(content: Text(message)));
                      } catch (_) {
                        if (!context.mounted) {
                          return;
                        }
                        final message = source == ImageSource.camera
                            ? 'Camera not available. Choose from gallery.'
                            : 'Unable to load photo.';
                        ScaffoldMessenger.of(
                          context,
                        ).showSnackBar(SnackBar(content: Text(message)));
                      }
                    },
                    label: const Text('+'),
                    backgroundColor: Theme.of(context).colorScheme.primary,
                    labelStyle: TextStyle(
                      color: Theme.of(context).colorScheme.onPrimary,
                      fontWeight: FontWeight.w600,
                    ),
                    side: BorderSide.none,
                  ),
                  const SizedBox(width: 8),
                  ActionChip(
                    onPressed: photos.isEmpty
                        ? null
                        : () {
                            setState(() {
                              photos = <_DraftPhoto>[];
                            });
                          },
                    label: const Text('Clear all'),
                    backgroundColor: Theme.of(context).colorScheme.primary,
                    disabledColor: Theme.of(
                      context,
                    ).colorScheme.surfaceContainerHighest,
                    labelStyle: TextStyle(
                      color: photos.isEmpty
                          ? Theme.of(context).colorScheme.onSurfaceVariant
                          : Theme.of(context).colorScheme.onPrimary,
                      fontWeight: FontWeight.w600,
                    ),
                    side: BorderSide.none,
                  ),
                  const Spacer(),
                  ActionChip(
                    onPressed: () => Navigator.of(dialogContext).pop(photos),
                    label: const Text('Done'),
                    backgroundColor: Theme.of(context).colorScheme.primary,
                    labelStyle: TextStyle(
                      color: Theme.of(context).colorScheme.onPrimary,
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
  }

  Future<ImageSource?> _choosePhotoSource(BuildContext context) async {
    return showModalBottomSheet<ImageSource>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined),
              title: const Text('Take photo'),
              onTap: () => Navigator.of(sheetContext).pop(ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Choose from gallery'),
              onTap: () => Navigator.of(sheetContext).pop(ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
  }

  Widget _section(
    BuildContext context, {
    required String title,
    required List<Widget> children,
    Widget? titleAction,
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
                      if (titleAction != null) ...[
                        const SizedBox(width: 4),
                        titleAction,
                      ],
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

  String _formatFindRowDateTime(String findDate, String findTime) {
    final date = findDate.trim();
    final time = findTime.trim();
    var mmdd = date;
    final dateParts = date.split('-');
    if (dateParts.length == 3 &&
        dateParts[1].length == 2 &&
        dateParts[2].length == 2) {
      mmdd = '${dateParts[1]}-${dateParts[2]}';
    }
    var hhmm = time;
    final timeParts = time.split(':');
    if (timeParts.length >= 2) {
      final hh = timeParts[0].padLeft(2, '0');
      final mm = timeParts[1].padLeft(2, '0');
      hhmm = '$hh:$mm';
    }
    if (mmdd.isEmpty) {
      return hhmm;
    }
    if (hhmm.isEmpty) {
      return mmdd;
    }
    return '$mmdd $hhmm';
  }

  String _teamMemberInitials(int teamMemberId) {
    for (final row in widget.trip.teamMembers) {
      if (row.id != teamMemberId) {
        continue;
      }
      final parts = row.name
          .trim()
          .split(RegExp(r'\s+'))
          .where((part) => part.isNotEmpty)
          .toList(growable: false);
      if (parts.isEmpty) {
        break;
      }
      if (parts.length == 1) {
        return parts.first.substring(0, 1).toUpperCase();
      }
      final first = parts.first.substring(0, 1).toUpperCase();
      final last = parts.last.substring(0, 1).toUpperCase();
      return '$first$last';
    }
    return 'NA';
  }

  Future<void> _reloadLocalFinds() async {
    final activeEventId = _activeCollectionEventId;
    final eventIds = activeEventId != null
        ? <int>[activeEventId]
        : widget.trip.collectionEvents
              .map((row) => row.id)
              .where((id) => id > 0)
              .toList(growable: false);
    if (!mounted) {
      return;
    }
    setState(() {
      _findsLoading = true;
    });
    try {
      final rows = await _localDb.listFindsLocalByCollectionEventIds(eventIds);
      final parsed = rows.map(_LocalFindRow.fromDbRow).toList(growable: false);
      if (!mounted) {
        return;
      }
      setState(() {
        _localFindRows = parsed;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _localFindRows = const <_LocalFindRow>[];
      });
    } finally {
      if (mounted) {
        setState(() {
          _findsLoading = false;
        });
      }
    }
  }

  Future<void> _openFindPhotosDialogForRow(_LocalFindRow row) async {
    var photos = await _localDb.listFindPhotosByFindLocalId(row.localId);
    if (!mounted) {
      return;
    }
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Row(
            children: [
              const Expanded(child: Text('Find Photos')),
              IconButton(
                onPressed: () => Navigator.of(dialogContext).pop(),
                tooltip: 'Close',
                icon: const Icon(Icons.close),
              ),
            ],
          ),
          content: SizedBox(
            width: 380,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Find: ${row.findDate} ${row.findTime}'),
                const SizedBox(height: 10),
                if (photos.isEmpty)
                  const Text('No photos associated with this find yet.'),
                if (photos.isNotEmpty)
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxHeight: 260),
                    child: Scrollbar(
                      thumbVisibility: false,
                      child: ListView.separated(
                        shrinkWrap: true,
                        itemCount: photos.length,
                        separatorBuilder: (context, index) =>
                            const SizedBox(height: 8),
                        itemBuilder: (context, index) {
                          final item = photos[index];
                          final filePath = (item['file_path'] ?? '')
                              .toString()
                              .trim();
                          final localPhotoId = (item['local_photo_id'] ?? '')
                              .toString()
                              .trim();
                          final source = (item['source'] ?? '')
                              .toString()
                              .trim();
                          final capturedAt = (item['captured_at_device'] ?? '')
                              .toString()
                              .trim();
                          final label = source.isEmpty ? 'Photo' : source;
                          return Dismissible(
                            key: ValueKey<String>(localPhotoId),
                            direction: DismissDirection.endToStart,
                            background: Container(
                              alignment: Alignment.centerRight,
                              padding: const EdgeInsets.symmetric(horizontal: 12),
                              decoration: BoxDecoration(
                                color: Theme.of(context).colorScheme.errorContainer,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Icon(
                                Icons.delete_outline,
                                color: Theme.of(context).colorScheme.onErrorContainer,
                              ),
                            ),
                            confirmDismiss: (_) async {
                              if (photos.length <= 1) {
                                if (!context.mounted) {
                                  return false;
                                }
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                      'A find must contain at least 1 photo.',
                                    ),
                                  ),
                                );
                                return false;
                              }
                              await _deleteFindPhotoForRow(item);
                              return true;
                            },
                            onDismissed: (_) {
                              setDialogState(() {
                                photos = photos
                                    .where(
                                      (photo) =>
                                          (photo['local_photo_id'] ?? '')
                                              .toString()
                                              .trim() !=
                                          localPhotoId,
                                    )
                                    .toList(growable: false);
                              });
                            },
                            child: Row(
                              children: [
                                GestureDetector(
                                  onTap: () async {
                                    await _openDraftPhotoViewer(
                                      context,
                                      _DraftPhoto(
                                        id: localPhotoId,
                                        label: label,
                                        capturedAtIso: capturedAt,
                                        filePath: filePath,
                                        source: source,
                                      ),
                                    );
                                  },
                                  child: Container(
                                    width: 64,
                                    height: 64,
                                    decoration: BoxDecoration(
                                      color: Theme.of(
                                        context,
                                      ).colorScheme.surfaceContainerHighest,
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(
                                        color: Theme.of(context).dividerColor,
                                      ),
                                    ),
                                    child:
                                        filePath.isNotEmpty &&
                                            File(filePath).existsSync()
                                        ? ClipRRect(
                                            borderRadius:
                                                BorderRadius.circular(8),
                                            child: Image.file(
                                              File(filePath),
                                              fit: BoxFit.cover,
                                            ),
                                          )
                                        : Icon(
                                            Icons.image_outlined,
                                            color: Theme.of(
                                              context,
                                            ).colorScheme.onSurfaceVariant,
                                          ),
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    '${_formatPhotoSource(source)} • $capturedAt',
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),
                  ),
              ],
            ),
          ),
          actions: [
            SizedBox(
              width: double.infinity,
              child: Row(
                children: [
                  ActionChip(
                    onPressed: () async {
                      final inserted = await _addPhotoToExistingFind(
                        row.localId,
                      );
                      if (inserted == false) {
                        return;
                      }
                      final refreshed = await _localDb
                          .listFindPhotosByFindLocalId(row.localId);
                      setDialogState(() {
                        photos = refreshed;
                      });
                    },
                    label: const Text('+'),
                    backgroundColor: Theme.of(context).colorScheme.primary,
                    labelStyle: TextStyle(
                      color: Theme.of(context).colorScheme.onPrimary,
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
  }

  Future<bool> _addPhotoToExistingFind(String findLocalId) async {
    final messenger = ScaffoldMessenger.maybeOf(context);
    final source = await _choosePhotoSource(context);
    if (source == null) {
      return false;
    }
    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(
        source: source,
        imageQuality: 85,
        maxWidth: 2200,
        maxHeight: 2200,
      );
      if (picked == null) {
        return false;
      }
      final now = DateTime.now().toUtc();
      final persistedPath = await _persistFindPhotoToLocalStorage(
        findLocalId: findLocalId,
        sourcePath: picked.path,
      );
      await _localDb.insertFindPhotoLocal(
        localPhotoId: 'findphoto-${now.microsecondsSinceEpoch}',
        findLocalId: findLocalId,
        filePath: persistedPath,
        source: source == ImageSource.camera ? 'camera' : 'gallery',
        capturedAtDevice: now.toIso8601String(),
        createdAtDevice: now.toIso8601String(),
        updatedAtDevice: now.toIso8601String(),
      );
      return true;
    } on PlatformException catch (exc) {
      final message = source == ImageSource.camera
          ? 'Camera not available. Choose from gallery.'
          : 'Unable to load photo.';
      messenger?.showSnackBar(
        SnackBar(content: Text('$message (${exc.message ?? 'plugin error'})')),
      );
      return false;
    } on MissingPluginException {
      final message = source == ImageSource.camera
          ? 'Camera not available. Choose from gallery.'
          : 'Unable to load photo.';
      messenger?.showSnackBar(SnackBar(content: Text(message)));
      return false;
    } catch (_) {
      final message = source == ImageSource.camera
          ? 'Camera not available. Choose from gallery.'
          : 'Unable to load photo.';
      messenger?.showSnackBar(SnackBar(content: Text(message)));
      return false;
    }
  }

  Future<void> _deleteFindPhotoForRow(Map<String, Object?> item) async {
    final localPhotoId = (item['local_photo_id'] ?? '').toString().trim();
    final filePath = (item['file_path'] ?? '').toString().trim();
    if (localPhotoId.isEmpty) {
      return;
    }
    try {
      await _localDb.deleteFindPhotoLocal(localPhotoId);
    } catch (_) {}
    if (filePath.isEmpty) {
      return;
    }
    try {
      final file = File(filePath);
      if (await file.exists()) {
        await file.delete();
      }
    } catch (_) {}
  }

  Future<String> _persistFindPhotoToLocalStorage({
    required String findLocalId,
    required String sourcePath,
  }) async {
    final raw = sourcePath.trim();
    if (raw.isEmpty) {
      return '';
    }
    final sourceFile = File(raw);
    if (!await sourceFile.exists()) {
      return raw;
    }
    try {
      final dbPath = await _localDb.resolveDatabasePath();
      final baseDir = p.dirname(dbPath);
      final outDir = Directory(p.join(baseDir, 'find_photos', findLocalId));
      if (!await outDir.exists()) {
        await outDir.create(recursive: true);
      }
      final ext = p.extension(raw);
      final outPath = p.join(
        outDir.path,
        '${DateTime.now().toUtc().microsecondsSinceEpoch}$ext',
      );
      await sourceFile.copy(outPath);
      return outPath;
    } catch (_) {
      return raw;
    }
  }

  Future<String> _persistDraftPhotoToLocalStorage(String sourcePath) async {
    final raw = sourcePath.trim();
    if (raw.isEmpty) {
      return '';
    }
    final sourceFile = File(raw);
    if (!await sourceFile.exists()) {
      return '';
    }
    try {
      final dbPath = await _localDb.resolveDatabasePath();
      final baseDir = p.dirname(dbPath);
      final outDir = Directory(p.join(baseDir, 'draft_photos'));
      if (!await outDir.exists()) {
        await outDir.create(recursive: true);
      }
      final ext = p.extension(raw);
      final outPath = p.join(
        outDir.path,
        '${DateTime.now().toUtc().microsecondsSinceEpoch}$ext',
      );
      await sourceFile.copy(outPath);
      return outPath;
    } catch (_) {
      return '';
    }
  }

  void _disposeControllersNextFrame(List<TextEditingController> controllers) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      for (final controller in controllers) {
        controller.dispose();
      }
    });
  }

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
    String title = 'Add Observations',
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
                Expanded(child: Text(title)),
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
                    Icon(
                      Icons.terrain,
                      size: 18,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '/',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Icon(
                      Icons.layers,
                      size: 18,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
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
      _disposeControllersNextFrame([provisionalController, notesController]);
    }
    return output;
  }

  Future<void> _openDraftPhotoViewer(
    BuildContext context,
    _DraftPhoto photo,
  ) async {
    final file = File(photo.filePath);
    final hasFile = file.existsSync();
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Row(
          children: [
            const Expanded(child: Text('Photo')),
            IconButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              tooltip: 'Close',
              icon: const Icon(Icons.close),
            ),
          ],
        ),
        content: SizedBox(
          width: 320,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 280,
                height: 220,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: Theme.of(context).dividerColor),
                ),
                child: hasFile
                    ? ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: Image.file(file, fit: BoxFit.cover),
                      )
                    : Icon(
                        Icons.image_outlined,
                        size: 72,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
              ),
              const SizedBox(height: 10),
              Text(
                '${_formatPhotoSource(photo.source)} • ${photo.capturedAtIso}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatPhotoSource(String source) {
    switch (source.trim().toLowerCase()) {
      case 'camera':
        return 'Camera';
      case 'gallery':
        return 'Gallery';
      default:
        return 'Unknown';
    }
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

class _DraftPhoto {
  const _DraftPhoto({
    required this.id,
    required this.label,
    required this.capturedAtIso,
    required this.filePath,
    required this.source,
  });

  final String id;
  final String label;
  final String capturedAtIso;
  final String filePath;
  final String source;
}

class _LocalFindRow {
  const _LocalFindRow({
    required this.localId,
    required this.collectionEventId,
    required this.teamMemberId,
    required this.source,
    required this.acceptedName,
    required this.findDate,
    required this.findTime,
    required this.provisionalIdentification,
    required this.abundValue,
    required this.notes,
    required this.latitude,
    required this.longitude,
    required this.syncStatus,
  });

  final String localId;
  final int collectionEventId;
  final int teamMemberId;
  final String source;
  final String acceptedName;
  final String findDate;
  final String findTime;
  final String? provisionalIdentification;
  final String? abundValue;
  final String? notes;
  final String? latitude;
  final String? longitude;
  final String syncStatus;

  factory _LocalFindRow.fromDbRow(Map<String, Object?> row) {
    String readText(String key, {String fallback = ''}) {
      final text = (row[key] ?? '').toString().trim();
      if (text.isEmpty) {
        return fallback;
      }
      return text;
    }

    int readInt(String key, {int fallback = 0}) {
      return int.tryParse((row[key] ?? '').toString()) ?? fallback;
    }

    String? readNullable(String key) {
      final text = (row[key] ?? '').toString().trim();
      if (text.isEmpty) {
        return null;
      }
      return text;
    }

    return _LocalFindRow(
      localId: readText('local_id'),
      collectionEventId: readInt('collection_event_id'),
      teamMemberId: readInt('team_member_id'),
      source: readText('source', fallback: 'Field'),
      acceptedName: readText('accepted_name', fallback: 'Unknown'),
      findDate: readText('find_date', fallback: '-'),
      findTime: readText('find_time', fallback: '-'),
      provisionalIdentification: readNullable('provisional_identification'),
      abundValue: readNullable('abund_value'),
      notes: readNullable('notes'),
      latitude: readNullable('latitude'),
      longitude: readNullable('longitude'),
      syncStatus: readText('sync_status', fallback: 'pending'),
    );
  }
}
