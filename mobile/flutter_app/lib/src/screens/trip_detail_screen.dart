import 'package:flutter/material.dart';

import '../models/trip_models.dart';

typedef CreateFindFn =
    Future<void> Function({
      required int collectionEventId,
      required String source,
      required String acceptedName,
    });

class TripDetailScreen extends StatefulWidget {
  const TripDetailScreen({
    super.key,
    required this.trip,
    required this.onCreateFind,
  });

  final TripDetail trip;
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
    final sourceController = TextEditingController();
    final acceptedController = TextEditingController();
    String? error;

    final result = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: const Text('New Find'),
            content: SizedBox(
              width: 420,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Collection Event ID: $eventId'),
                  const SizedBox(height: 10),
                  TextField(
                    controller: sourceController,
                    decoration: const InputDecoration(labelText: 'Source'),
                  ),
                  TextField(
                    controller: acceptedController,
                    decoration: const InputDecoration(
                      labelText: 'Accepted name',
                    ),
                  ),
                  if (error != null) ...[
                    const SizedBox(height: 10),
                    Text(error!, style: const TextStyle(color: Colors.red)),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(dialogContext).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () {
                  final source = sourceController.text.trim();
                  final accepted = acceptedController.text.trim();
                  if (source.isEmpty || accepted.isEmpty) {
                    setDialogState(() {
                      error = 'Source and Accepted name are required.';
                    });
                    return;
                  }
                  Navigator.of(dialogContext).pop(true);
                },
                child: const Text('Create'),
              ),
            ],
          ),
        );
      },
    );

    if (result != true) {
      sourceController.dispose();
      acceptedController.dispose();
      return;
    }

    setState(() {
      _savingFind = true;
    });
    try {
      await widget.onCreateFind(
        collectionEventId: eventId,
        source: sourceController.text.trim(),
        acceptedName: acceptedController.text.trim(),
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
      sourceController.dispose();
      acceptedController.dispose();
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
}
