import 'package:flutter/material.dart';

import '../models/trip_models.dart';

class TripsScreen extends StatelessWidget {
  const TripsScreen({
    super.key,
    required this.trips,
    required this.loading,
    required this.errorText,
    required this.onRefresh,
    required this.onOpenTrip,
    required this.onLogout,
  });

  final List<TripSummary> trips;
  final bool loading;
  final String? errorText;
  final Future<void> Function() onRefresh;
  final Future<void> Function(TripSummary trip) onOpenTrip;
  final Future<void> Function() onLogout;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Current Trips'),
        actions: [
          IconButton(
            onPressed: () => onLogout(),
            icon: const Icon(Icons.logout),
            tooltip: 'Sign Out',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: onRefresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(12),
          children: [
            if ((errorText ?? '').isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Card(
                  color: Theme.of(context).colorScheme.errorContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(10),
                    child: Text(errorText!),
                  ),
                ),
              ),
            if (loading)
              const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator())),
            if (!loading && trips.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 24),
                child: Center(child: Text('No current trips available.')),
              ),
            ...trips.map(
              (trip) => Card(
                child: ListTile(
                  title: Text(trip.tripName),
                  subtitle: Text(_summaryText(trip)),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => onOpenTrip(trip),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _summaryText(TripSummary trip) {
    final buffer = <String>[
      if ((trip.startDate ?? '').isNotEmpty) 'Start: ${trip.startDate}',
      if ((trip.endDate ?? '').isNotEmpty) 'End: ${trip.endDate}',
      if ((trip.location ?? '').isNotEmpty) 'Location: ${trip.location}',
      if ((trip.notes ?? '').isNotEmpty) 'Notes: ${trip.notes}',
    ];
    if (buffer.isEmpty) {
      return 'Tap to view trip details';
    }
    return buffer.join(' • ');
  }
}
