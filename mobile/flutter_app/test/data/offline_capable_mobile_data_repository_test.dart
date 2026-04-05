import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:paleo_mobile/src/api/api_client.dart';
import 'package:paleo_mobile/src/data/mobile_data_repository.dart';
import 'package:paleo_mobile/src/data/offline_capable_mobile_data_repository.dart';
import 'package:paleo_mobile/src/local_db/app_local_database.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  late AppLocalDatabase localDb;
  late OfflineCapableMobileDataRepository repository;

  setUpAll(() {
    sqfliteFfiInit();
  });

  setUp(() {
    localDb = AppLocalDatabase(
      databaseFactoryOverride: databaseFactoryFfi,
      databasePathOverride: inMemoryDatabasePath,
      databaseName: 'offline_repo_test.db',
    );
    repository = OfflineCapableMobileDataRepository(
      apiClient: ApiClient(baseUrl: 'https://example.invalid'),
      localDatabase: localDb,
    );
  });

  tearDown(() async {
    await localDb.close();
  });

  test('createFind stores pending local row and enqueues sync job', () async {
    await repository.createFind(
      collectionEventId: 44,
      teamMemberId: 7,
      findDate: '2026-04-03',
      findTime: '08:30',
      photos: const <CreateFindPhotoInput>[
        CreateFindPhotoInput(
          filePath: '/tmp/p1.jpg',
          source: 'gallery',
          capturedAtIso: '2026-04-03T08:29:00Z',
        ),
      ],
      latitude: '-19.25',
      longitude: '146.82',
    );

    final db = await localDb.database();
    final findsRows = await db.query('finds_local');
    final queueRows = await db.query('sync_queue');

    expect(findsRows, hasLength(1));
    expect(queueRows, hasLength(1));

    final find = findsRows.first;
    expect(find['collection_event_id'], 44);
    expect(find['team_member_id'], 7);
    expect(find['source'], 'Field');
    expect(find['accepted_name'], 'Unknown');
    expect(find['find_date'], '2026-04-03');
    expect(find['find_time'], '08:30');
    expect(find['latitude'], '-19.25');
    expect(find['longitude'], '146.82');
    expect(find['sync_status'], 'pending');

    final queue = queueRows.first;
    expect(queue['entity_type'], 'find');
    expect(queue['entity_local_id'], find['local_id']);
    expect(queue['operation'], 'create');

    final payload = jsonDecode((queue['payload_json'] ?? '').toString());
    expect(payload, isA<Map<String, dynamic>>());
    expect(payload['collection_event_id'], 44);
    expect(payload['team_member_id'], 7);
    expect(payload['source'], 'Field');
    expect(payload['accepted_name'], 'Unknown');
    expect(payload['find_date'], '2026-04-03');
    expect(payload['find_time'], '08:30');
    expect(payload['latitude'], '-19.25');
    expect(payload['longitude'], '146.82');
  });

  test('syncPending uploads queued find and marks it synced', () async {
    String? capturedIdempotencyKey;
    final mockClient = MockClient((http.Request request) async {
      if (request.url.path == '/v1/finds' && request.method == 'POST') {
        capturedIdempotencyKey = request.headers['Idempotency-Key'];
        return http.Response(
          '{"status":"accepted","message":"ok"}',
          200,
          headers: <String, String>{'content-type': 'application/json'},
        );
      }
      return http.Response('{"detail":"not found"}', 404);
    });

    repository = OfflineCapableMobileDataRepository(
      apiClient: ApiClient(baseUrl: 'https://example.test', client: mockClient),
      localDatabase: localDb,
    );
    repository.setTokens(
      accessToken: 'test-access',
      refreshToken: 'test-refresh',
    );

    await repository.createFind(
      collectionEventId: 101,
      teamMemberId: 8,
      findDate: '2026-04-03',
      findTime: '09:00',
      photos: const <CreateFindPhotoInput>[
        CreateFindPhotoInput(
          filePath: '/tmp/p2.jpg',
          source: 'camera',
          capturedAtIso: '2026-04-03T08:59:00Z',
        ),
      ],
    );
    final dbBeforeSync = await localDb.database();
    final queuedBeforeSync = await dbBeforeSync.query('sync_queue');
    expect(queuedBeforeSync, hasLength(1));
    final expectedIdempotencyKey =
        (queuedBeforeSync.first['idempotency_key'] ?? '').toString();
    await repository.syncPending();

    final db = await localDb.database();
    final queueRows = await db.query('sync_queue');
    final findRows = await db.query('finds_local');

    expect(queueRows, isEmpty);
    expect(findRows, hasLength(1));
    expect(findRows.first['sync_status'], 'synced');
    expect(findRows.first['last_error'], isNull);
    expect(capturedIdempotencyKey, expectedIdempotencyKey);
  });

  test('syncPending failure keeps queue and schedules retry', () async {
    final mockClient = MockClient((http.Request request) async {
      if (request.url.path == '/v1/finds' && request.method == 'POST') {
        return http.Response('{"detail":"temporary error"}', 503);
      }
      return http.Response('{"detail":"not found"}', 404);
    });

    repository = OfflineCapableMobileDataRepository(
      apiClient: ApiClient(baseUrl: 'https://example.test', client: mockClient),
      localDatabase: localDb,
    );
    repository.setTokens(
      accessToken: 'test-access',
      refreshToken: 'test-refresh',
    );

    await repository.createFind(
      collectionEventId: 202,
      teamMemberId: 9,
      findDate: '2026-04-03',
      findTime: '09:10',
      photos: const <CreateFindPhotoInput>[
        CreateFindPhotoInput(
          filePath: '/tmp/p3.jpg',
          source: 'gallery',
          capturedAtIso: '2026-04-03T09:09:00Z',
        ),
      ],
    );
    await repository.syncPending();

    final db = await localDb.database();
    final queueRows = await db.query('sync_queue');
    final findRows = await db.query('finds_local');

    expect(queueRows, hasLength(1));
    expect((queueRows.first['attempt_count'] as int?) ?? 0, 1);
    expect(findRows, hasLength(1));
    expect(findRows.first['sync_status'], 'failed');
    expect((findRows.first['last_error'] ?? '').toString(), contains('503'));
  });
}
