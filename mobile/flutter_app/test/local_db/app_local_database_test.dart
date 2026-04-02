import 'package:flutter_test/flutter_test.dart';
import 'package:paleo_mobile/src/local_db/app_local_database.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  late AppLocalDatabase localDb;
  late Database db;

  setUpAll(() {
    sqfliteFfiInit();
  });

  setUp(() async {
    localDb = AppLocalDatabase(
      databaseFactoryOverride: databaseFactoryFfi,
      databasePathOverride: inMemoryDatabasePath,
      databaseName: 'offline_test.db',
    );
    db = await localDb.database();
  });

  tearDown(() async {
    await localDb.close();
  });

  test('creates offline schema tables on first open', () async {
    final rows = await db.rawQuery(
      "SELECT name FROM sqlite_master WHERE type = 'table'",
    );
    final tableNames = rows
        .map((row) => (row['name'] ?? '').toString())
        .toSet();

    expect(tableNames, contains('trips'));
    expect(tableNames, contains('trip_details_cache'));
    expect(tableNames, contains('finds_local'));
    expect(tableNames, contains('sync_queue'));
    expect(tableNames, contains('sync_state'));
  });

  test('supports basic CRUD for core offline entities', () async {
    await localDb.upsertTrip(
      id: 12,
      tripName: 'JCU (2026/1)',
      startDate: '2026-05-01',
      endDate: '2026-05-10',
      location: 'Townsville',
      notes: 'Initial import',
      team: 'Alice; Bob',
      updatedAtServer: '2026-04-02T10:00:00Z',
    );
    await localDb.upsertTrip(
      id: 12,
      tripName: 'JCU (2026/1) - Updated',
      updatedAtServer: '2026-04-02T11:00:00Z',
    );
    final trips = await localDb.listTrips();
    expect(trips, hasLength(1));
    expect(trips.first['trip_name'], 'JCU (2026/1) - Updated');

    await localDb.upsertTripDetailCache(
      tripId: 12,
      payloadJson: '{"id":12,"trip_name":"JCU (2026/1)"}',
      updatedAtServer: '2026-04-02T11:00:00Z',
    );
    final detailRows = await db.query('trip_details_cache');
    expect(detailRows, hasLength(1));

    await localDb.upsertFindLocal(
      localId: 'local-find-1',
      collectionEventId: 77,
      teamMemberId: 7,
      source: 'Field',
      acceptedName: 'Unknown',
      findDate: '2026-04-03',
      findTime: '10:15',
      latitude: '-19.2500',
      longitude: '146.8200',
      createdAtDevice: '2026-04-02T12:00:00Z',
      updatedAtDevice: '2026-04-02T12:00:00Z',
      syncStatus: 'pending',
    );
    final localFinds = await db.query('finds_local');
    expect(localFinds, hasLength(1));
    expect(localFinds.first['sync_status'], 'pending');
    expect(localFinds.first['team_member_id'], 7);
    expect(localFinds.first['find_date'], '2026-04-03');
    expect(localFinds.first['find_time'], '10:15');
    expect(localFinds.first['latitude'], '-19.2500');
    expect(localFinds.first['longitude'], '146.8200');

    final insertedQueueId = await localDb.enqueueSyncQueue(
      entityType: 'find',
      entityLocalId: 'local-find-1',
      operation: 'create',
      idempotencyKey: 'idem-123',
      payloadJson:
          '{"collection_event_id":77,"source":"Field","accepted_name":"Unknown","find_date":"2026-04-03","find_time":"10:15","latitude":"-19.2500","longitude":"146.8200"}',
      nextAttemptAt: '2026-04-02T12:00:00Z',
      createdAt: '2026-04-02T12:00:00Z',
      updatedAt: '2026-04-02T12:00:00Z',
    );
    expect(insertedQueueId, greaterThan(0));
    expect(await localDb.pendingSyncQueueCount(), 1);

    await localDb.setSyncState(
      'last_successful_sync_at',
      '2026-04-02T12:05:00Z',
    );
    final syncCursor = await localDb.getSyncState('last_successful_sync_at');
    expect(syncCursor, '2026-04-02T12:05:00Z');
  });
}
