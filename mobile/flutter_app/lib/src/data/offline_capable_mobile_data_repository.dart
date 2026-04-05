import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:path/path.dart' as p;

import '../api/api_client.dart';
import '../local_db/app_local_database.dart';
import '../models/auth_models.dart';
import '../models/trip_models.dart';
import 'mobile_data_repository.dart';

class OfflineCapableMobileDataRepository implements MobileDataRepository {
  OfflineCapableMobileDataRepository({
    required ApiClient apiClient,
    required AppLocalDatabase localDatabase,
  }) : _apiClient = apiClient,
       _localDatabase = localDatabase;

  final ApiClient _apiClient;
  final AppLocalDatabase _localDatabase;
  final Random _random = Random.secure();

  @override
  void setTokens({required String accessToken, required String refreshToken}) {
    _apiClient.setTokens(accessToken: accessToken, refreshToken: refreshToken);
  }

  @override
  void clearTokens() {
    _apiClient.clearTokens();
  }

  @override
  Future<LoginResult> login({
    required String username,
    required String password,
  }) async {
    try {
      return await _apiClient.login(username: username, password: password);
    } on ApiClientError catch (exc) {
      throw MobileDataRepositoryError(exc.message);
    }
  }

  @override
  Future<AuthUser> me() async {
    try {
      return await _apiClient.me();
    } on ApiClientError catch (exc) {
      throw MobileDataRepositoryError(exc.message);
    }
  }

  @override
  Future<List<TripSummary>> listCurrentTrips() async {
    try {
      final trips = await _apiClient.listCurrentTrips();
      final updatedAt = DateTime.now().toUtc().toIso8601String();
      for (final trip in trips) {
        await _localDatabase.upsertTrip(
          id: trip.id,
          tripName: trip.tripName,
          startDate: trip.startDate,
          endDate: trip.endDate,
          location: trip.location,
          notes: trip.notes,
          team: trip.team,
          updatedAtServer: updatedAt,
        );
      }
      return trips;
    } on ApiClientError catch (exc) {
      final cachedRows = await _localDatabase.listTrips();
      if (cachedRows.isNotEmpty) {
        return cachedRows.map(_tripSummaryFromLocalRow).toList(growable: false);
      }
      throw MobileDataRepositoryError(exc.message);
    }
  }

  @override
  Future<TripDetail> getTripDetail(int tripId) async {
    try {
      final detail = await _apiClient.getTripDetail(tripId);
      await _localDatabase.upsertTripDetailCache(
        tripId: tripId,
        payloadJson: jsonEncode(<String, Object?>{
          'id': detail.id,
          'trip_name': detail.tripName,
          'can_view_details': detail.canViewDetails,
          'start_date': detail.startDate,
          'end_date': detail.endDate,
          'location': detail.location,
          'notes': detail.notes,
          'team': detail.team,
          'find_count': detail.findCount,
          'team_members': detail.teamMembers
              .map((m) => <String, Object?>{'id': m.id, 'name': m.name})
              .toList(growable: false),
          'locations': detail.locations
              .map((l) => <String, Object?>{'id': l.id, 'name': l.name})
              .toList(growable: false),
          'collection_events': detail.collectionEvents
              .map(
                (e) => <String, Object?>{
                  'id': e.id,
                  'collection_name': e.collectionName,
                  'event_year': e.eventYear,
                  'boundary_geojson': e.boundaryGeojson,
                },
              )
              .toList(growable: false),
        }),
        updatedAtServer: DateTime.now().toUtc().toIso8601String(),
      );
      return _withUnsyncedLocalFinds(detail);
    } on ApiClientError catch (exc) {
      final cachedPayload = await _localDatabase.getTripDetailPayload(tripId);
      if (cachedPayload != null) {
        final cached = TripDetail.fromJson(cachedPayload);
        return _withUnsyncedLocalFinds(cached);
      }
      throw MobileDataRepositoryError(exc.message);
    }
  }

  @override
  Future<void> createFind({
    required int collectionEventId,
    required int teamMemberId,
    required String findDate,
    required String findTime,
    required List<CreateFindPhotoInput> photos,
    String? provisionalIdentification,
    String? latitude,
    String? longitude,
  }) async {
    if (photos.isEmpty) {
      throw MobileDataRepositoryError(
        'Cannot create find without at least one associated photo.',
      );
    }
    final now = DateTime.now().toUtc().toIso8601String();
    final localId = _newClientId('find');
    final idempotencyKey = _newClientId('idem');
    final payload = <String, Object?>{
      'collection_event_id': collectionEventId,
      'team_member_id': teamMemberId,
      'source': 'Field',
      'accepted_name': 'Unknown',
      'find_date': findDate,
      'find_time': findTime,
      'latitude': latitude,
      'longitude': longitude,
    };

    try {
      await _localDatabase.upsertFindLocal(
        localId: localId,
        collectionEventId: collectionEventId,
        teamMemberId: teamMemberId,
        source: 'Field',
        acceptedName: 'Unknown',
        findDate: findDate,
        findTime: findTime,
        provisionalIdentification: provisionalIdentification,
        latitude: latitude,
        longitude: longitude,
        createdAtDevice: now,
        updatedAtDevice: now,
        syncStatus: 'pending',
      );
      for (final photo in photos) {
        final persistedPath = await _persistPhotoPath(
          findLocalId: localId,
          sourcePath: photo.filePath,
        );
        await _localDatabase.insertFindPhotoLocal(
          localPhotoId: _newClientId('findphoto'),
          findLocalId: localId,
          filePath: persistedPath,
          source: photo.source,
          capturedAtDevice: photo.capturedAtIso,
          createdAtDevice: now,
          updatedAtDevice: now,
        );
      }
      await _localDatabase.enqueueSyncQueue(
        entityType: 'find',
        entityLocalId: localId,
        operation: 'create',
        idempotencyKey: idempotencyKey,
        payloadJson: jsonEncode(payload),
        nextAttemptAt: now,
        createdAt: now,
        updatedAt: now,
      );
    } catch (exc) {
      throw MobileDataRepositoryError('Failed to queue offline find: $exc');
    }
  }

  @override
  Future<void> syncPending() async {
    if ((_apiClient.accessToken ?? '').isEmpty) {
      return;
    }
    final now = DateTime.now().toUtc();
    final dueItems = await _localDatabase.listDueSyncQueueItems(
      nowIsoUtc: now.toIso8601String(),
      limit: 25,
    );
    for (final item in dueItems) {
      await _syncQueueItem(item);
    }
  }

  @override
  Future<SyncSnapshot> getSyncSnapshot() async {
    try {
      final pendingCount = await _localDatabase.pendingSyncQueueCount();
      final failedCount = await _localDatabase.countFindsBySyncStatus('failed');
      return SyncSnapshot(pendingCount: pendingCount, failedCount: failedCount);
    } catch (_) {
      return const SyncSnapshot(pendingCount: 0, failedCount: 0);
    }
  }

  TripSummary _tripSummaryFromLocalRow(Map<String, Object?> row) {
    return TripSummary(
      id: (row['id'] as int?) ?? 0,
      tripName: (row['trip_name'] ?? '').toString(),
      startDate: _nullableText(row['start_date']),
      endDate: _nullableText(row['end_date']),
      location: _nullableText(row['location']),
      notes: _nullableText(row['notes']),
      team: _nullableText(row['team']),
    );
  }

  String? _nullableText(Object? value) {
    final text = (value ?? '').toString().trim();
    if (text.isEmpty) {
      return null;
    }
    return text;
  }

  String _newClientId(String prefix) {
    final ts = DateTime.now().toUtc().microsecondsSinceEpoch;
    final rand = _random.nextInt(1 << 32);
    return '$prefix-$ts-$rand';
  }

  Future<void> _syncQueueItem(Map<String, Object?> row) async {
    final id = (row['id'] as int?) ?? 0;
    final entityType = (row['entity_type'] ?? '').toString();
    final operation = (row['operation'] ?? '').toString();
    final entityLocalId = (row['entity_local_id'] ?? '').toString();
    final payloadRaw = (row['payload_json'] ?? '').toString();
    final idempotencyKey = (row['idempotency_key'] ?? '').toString();
    final previousAttempts = (row['attempt_count'] as int?) ?? 0;

    if (id <= 0 || entityType != 'find' || operation != 'create') {
      await _localDatabase.deleteSyncQueueItem(id);
      return;
    }

    await _localDatabase.setFindLocalSyncState(
      localId: entityLocalId,
      syncStatus: 'syncing',
      lastError: null,
    );

    try {
      final payload = jsonDecode(payloadRaw);
      if (payload is! Map<String, dynamic>) {
        throw const FormatException('Invalid sync payload format.');
      }
      final teamMemberId = int.tryParse(
        (payload['team_member_id'] ?? '').toString(),
      );
      await _apiClient.createFind(
        collectionEventId: int.parse(payload['collection_event_id'].toString()),
        teamMemberId: teamMemberId,
        findDate: (payload['find_date'] ?? '').toString(),
        findTime: (payload['find_time'] ?? '').toString(),
        latitude: _nullableText(payload['latitude']),
        longitude: _nullableText(payload['longitude']),
        idempotencyKey: idempotencyKey,
      );
      await _localDatabase.deleteSyncQueueItem(id);
      await _localDatabase.setFindLocalSyncState(
        localId: entityLocalId,
        syncStatus: 'synced',
        lastError: null,
      );
    } on ApiClientError catch (exc) {
      await _markRetry(
        queueId: id,
        entityLocalId: entityLocalId,
        previousAttempts: previousAttempts,
        errorText: exc.message,
      );
    } on FormatException catch (exc) {
      await _markRetry(
        queueId: id,
        entityLocalId: entityLocalId,
        previousAttempts: previousAttempts,
        errorText: exc.message,
      );
    } catch (exc) {
      await _markRetry(
        queueId: id,
        entityLocalId: entityLocalId,
        previousAttempts: previousAttempts,
        errorText: exc.toString(),
      );
    }
  }

  Future<void> _markRetry({
    required int queueId,
    required String entityLocalId,
    required int previousAttempts,
    required String errorText,
  }) async {
    final nextAttempts = previousAttempts + 1;
    final delaySeconds = min(15 * 60, 5 * (1 << min(previousAttempts, 7)));
    final now = DateTime.now().toUtc();
    final nextAttemptAt = now.add(Duration(seconds: delaySeconds));
    await _localDatabase.updateSyncQueueRetry(
      id: queueId,
      attemptCount: nextAttempts,
      nextAttemptAt: nextAttemptAt.toIso8601String(),
      updatedAt: now.toIso8601String(),
    );
    await _localDatabase.setFindLocalSyncState(
      localId: entityLocalId,
      syncStatus: 'failed',
      lastError: errorText,
    );
  }

  Future<String> _persistPhotoPath({
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
      final dbPath = await _localDatabase.resolveDatabasePath();
      final dbDir = p.dirname(dbPath);
      final outDir = Directory(p.join(dbDir, 'find_photos', findLocalId));
      if (!await outDir.exists()) {
        await outDir.create(recursive: true);
      }
      final ext = p.extension(raw);
      final outName = '${DateTime.now().toUtc().microsecondsSinceEpoch}$ext';
      final outPath = p.join(outDir.path, outName);
      await sourceFile.copy(outPath);
      return outPath;
    } catch (_) {
      return raw;
    }
  }

  Future<TripDetail> _withUnsyncedLocalFinds(TripDetail detail) async {
    final eventIds = detail.collectionEvents
        .map((e) => e.id)
        .where((id) => id > 0)
        .toList(growable: false);
    if (eventIds.isEmpty) {
      return detail;
    }
    final unsyncedCount = await _localDatabase
        .countUnsyncedFindsByCollectionEventIds(eventIds);
    if (unsyncedCount <= 0) {
      return detail;
    }
    final baseCount = detail.findCount ?? 0;
    return TripDetail(
      id: detail.id,
      tripName: detail.tripName,
      canViewDetails: detail.canViewDetails,
      startDate: detail.startDate,
      endDate: detail.endDate,
      location: detail.location,
      notes: detail.notes,
      team: detail.team,
      findCount: baseCount + unsyncedCount,
      teamMembers: detail.teamMembers,
      locations: detail.locations,
      collectionEvents: detail.collectionEvents,
    );
  }
}
