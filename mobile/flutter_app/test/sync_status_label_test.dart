import 'package:flutter_test/flutter_test.dart';
import 'package:paleo_mobile/main.dart';

void main() {
  test('resolveSyncStatusLabel prefers Offline when disconnected', () {
    final label = resolveSyncStatusLabel(
      isOnline: false,
      syncInProgress: false,
      pendingCount: 10,
      failedCount: 10,
    );
    expect(label, 'Offline');
  });

  test('resolveSyncStatusLabel shows Syncing for active sync or pending queue', () {
    expect(
      resolveSyncStatusLabel(
        isOnline: true,
        syncInProgress: true,
        pendingCount: 0,
        failedCount: 0,
      ),
      'Syncing',
    );
    expect(
      resolveSyncStatusLabel(
        isOnline: true,
        syncInProgress: false,
        pendingCount: 1,
        failedCount: 0,
      ),
      'Syncing',
    );
  });

  test('resolveSyncStatusLabel shows Needs attention for failures', () {
    final label = resolveSyncStatusLabel(
      isOnline: true,
      syncInProgress: false,
      pendingCount: 0,
      failedCount: 2,
    );
    expect(label, 'Needs attention');
  });

  test('resolveSyncStatusLabel shows Synced when clear', () {
    final label = resolveSyncStatusLabel(
      isOnline: true,
      syncInProgress: false,
      pendingCount: 0,
      failedCount: 0,
    );
    expect(label, 'Synced');
  });
}
