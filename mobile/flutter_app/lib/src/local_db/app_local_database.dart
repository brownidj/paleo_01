import 'dart:convert';

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

class AppLocalDatabase {
  AppLocalDatabase({
    DatabaseFactory? databaseFactoryOverride,
    String? databasePathOverride,
    this.databaseName = defaultDatabaseName,
  }) : _databaseFactoryOverride = databaseFactoryOverride,
       _databasePathOverride = databasePathOverride;

  static const String defaultDatabaseName = 'paleo_mobile.db';
  static const int schemaVersion = 5;

  final DatabaseFactory? _databaseFactoryOverride;
  final String? _databasePathOverride;
  final String databaseName;

  Database? _database;

  Future<Database> database() async {
    final existing = _database;
    if (existing != null && existing.isOpen) {
      return existing;
    }
    final dbFactory = _databaseFactoryOverride ?? databaseFactory;
    final dbPath =
        _databasePathOverride ??
        p.join(await dbFactory.getDatabasesPath(), databaseName);
    final db = await dbFactory.openDatabase(
      dbPath,
      options: OpenDatabaseOptions(
        version: schemaVersion,
        onCreate: _onCreate,
        onUpgrade: _onUpgrade,
      ),
    );
    _database = db;
    return db;
  }

  Future<void> close() async {
    final db = _database;
    if (db == null) {
      return;
    }
    await db.close();
    _database = null;
  }

  Future<String> resolveDatabasePath() async {
    final db = await database();
    return db.path;
  }

  Future<void> deleteDatabaseFile() async {
    final dbFactory = _databaseFactoryOverride ?? databaseFactory;
    final dbPath =
        _databasePathOverride ??
        p.join(await dbFactory.getDatabasesPath(), databaseName);
    await close();
    await dbFactory.deleteDatabase(dbPath);
  }

  Future<List<Map<String, Object?>>> listTrips() async {
    final db = await database();
    return db.query(
      'trips',
      orderBy:
          "CASE WHEN start_date IS NULL OR TRIM(start_date) = '' THEN 1 ELSE 0 END ASC, start_date ASC, trip_name ASC, id ASC",
    );
  }

  Future<void> upsertTrip({
    required int id,
    required String tripName,
    String? startDate,
    String? endDate,
    String? location,
    String? notes,
    String? team,
    required String updatedAtServer,
  }) async {
    final db = await database();
    await db.insert('trips', <String, Object?>{
      'id': id,
      'trip_name': tripName,
      'start_date': startDate,
      'end_date': endDate,
      'location': location,
      'notes': notes,
      'team': team,
      'updated_at_server': updatedAtServer,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertTripDetailCache({
    required int tripId,
    required String payloadJson,
    required String updatedAtServer,
  }) async {
    final db = await database();
    await db.insert('trip_details_cache', <String, Object?>{
      'trip_id': tripId,
      'payload_json': payloadJson,
      'updated_at_server': updatedAtServer,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<Map<String, dynamic>?> getTripDetailPayload(int tripId) async {
    final db = await database();
    final rows = await db.query(
      'trip_details_cache',
      columns: <String>['payload_json'],
      where: 'trip_id = ?',
      whereArgs: <Object?>[tripId],
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }
    final rawPayload = (rows.first['payload_json'] ?? '').toString();
    if (rawPayload.isEmpty) {
      return null;
    }
    final decoded = jsonDecode(rawPayload);
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    return null;
  }

  Future<void> upsertFindLocal({
    required String localId,
    int? serverId,
    required int collectionEventId,
    required int teamMemberId,
    required String source,
    required String acceptedName,
    required String findDate,
    required String findTime,
    String? provisionalIdentification,
    String? abundValue,
    String? notes,
    String? latitude,
    String? longitude,
    required String createdAtDevice,
    required String updatedAtDevice,
    String? deletedAtDevice,
    required String syncStatus,
    String? lastError,
  }) async {
    final db = await database();
    await db.insert('finds_local', <String, Object?>{
      'local_id': localId,
      'server_id': serverId,
      'collection_event_id': collectionEventId,
      'team_member_id': teamMemberId,
      'source': source,
      'accepted_name': acceptedName,
      'find_date': findDate,
      'find_time': findTime,
      'provisional_identification': provisionalIdentification,
      'abund_value': abundValue,
      'notes': notes,
      'latitude': latitude,
      'longitude': longitude,
      'created_at_device': createdAtDevice,
      'updated_at_device': updatedAtDevice,
      'deleted_at_device': deletedAtDevice,
      'sync_status': syncStatus,
      'last_error': lastError,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<int> enqueueSyncQueue({
    required String entityType,
    required String entityLocalId,
    required String operation,
    required String idempotencyKey,
    required String payloadJson,
    required String nextAttemptAt,
    required String createdAt,
    required String updatedAt,
  }) async {
    final db = await database();
    return db.insert('sync_queue', <String, Object?>{
      'entity_type': entityType,
      'entity_local_id': entityLocalId,
      'operation': operation,
      'idempotency_key': idempotencyKey,
      'payload_json': payloadJson,
      'next_attempt_at': nextAttemptAt,
      'created_at': createdAt,
      'updated_at': updatedAt,
    });
  }

  Future<int> pendingSyncQueueCount() async {
    final db = await database();
    final rows = await db.rawQuery('SELECT COUNT(*) AS count FROM sync_queue');
    if (rows.isEmpty) {
      return 0;
    }
    return (rows.first['count'] as int?) ?? 0;
  }

  Future<int> countFindsBySyncStatus(String syncStatus) async {
    final db = await database();
    final rows = await db.rawQuery(
      'SELECT COUNT(*) AS count FROM finds_local WHERE sync_status = ?',
      <Object?>[syncStatus],
    );
    if (rows.isEmpty) {
      return 0;
    }
    return (rows.first['count'] as int?) ?? 0;
  }

  Future<int> countUnsyncedFindsByCollectionEventIds(
    List<int> collectionEventIds,
  ) async {
    if (collectionEventIds.isEmpty) {
      return 0;
    }
    final db = await database();
    final placeholders = List<String>.filled(
      collectionEventIds.length,
      '?',
    ).join(',');
    final rows = await db.rawQuery('''
      SELECT COUNT(*) AS count
      FROM finds_local
      WHERE collection_event_id IN ($placeholders)
        AND sync_status IN ('pending', 'syncing', 'failed', 'conflict')
        AND (deleted_at_device IS NULL OR TRIM(deleted_at_device) = '')
      ''', collectionEventIds.cast<Object?>());
    if (rows.isEmpty) {
      return 0;
    }
    return (rows.first['count'] as int?) ?? 0;
  }

  Future<List<Map<String, Object?>>> listDueSyncQueueItems({
    required String nowIsoUtc,
    int limit = 25,
  }) async {
    final db = await database();
    return db.query(
      'sync_queue',
      where: 'next_attempt_at <= ?',
      whereArgs: <Object?>[nowIsoUtc],
      orderBy: 'id ASC',
      limit: limit,
    );
  }

  Future<void> updateSyncQueueRetry({
    required int id,
    required int attemptCount,
    required String nextAttemptAt,
    required String updatedAt,
  }) async {
    final db = await database();
    await db.update(
      'sync_queue',
      <String, Object?>{
        'attempt_count': attemptCount,
        'next_attempt_at': nextAttemptAt,
        'updated_at': updatedAt,
      },
      where: 'id = ?',
      whereArgs: <Object?>[id],
    );
  }

  Future<void> deleteSyncQueueItem(int id) async {
    final db = await database();
    await db.delete('sync_queue', where: 'id = ?', whereArgs: <Object?>[id]);
  }

  Future<void> setFindLocalSyncState({
    required String localId,
    required String syncStatus,
    String? lastError,
    int? serverId,
  }) async {
    final db = await database();
    final values = <String, Object?>{
      'sync_status': syncStatus,
      'last_error': lastError,
      'updated_at_device': DateTime.now().toUtc().toIso8601String(),
    };
    if (serverId != null) {
      values['server_id'] = serverId;
    }
    await db.update(
      'finds_local',
      values,
      where: 'local_id = ?',
      whereArgs: <Object?>[localId],
    );
  }

  Future<void> setSyncState(String key, String value) async {
    final db = await database();
    await db.insert('sync_state', <String, Object?>{
      'key': key,
      'value': value,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<String?> getSyncState(String key) async {
    final db = await database();
    final rows = await db.query(
      'sync_state',
      columns: <String>['value'],
      where: 'key = ?',
      whereArgs: <Object?>[key],
      limit: 1,
    );
    if (rows.isEmpty) {
      return null;
    }
    return rows.first['value'] as String?;
  }

  Future<List<Map<String, Object?>>> listFindsLocalByCollectionEventIds(
    List<int> collectionEventIds, {
    int limit = 200,
  }) async {
    if (collectionEventIds.isEmpty) {
      return const <Map<String, Object?>>[];
    }
    final db = await database();
    final placeholders = List<String>.filled(
      collectionEventIds.length,
      '?',
    ).join(',');
    return db.rawQuery(
      '''
      SELECT
        local_id,
        server_id,
        collection_event_id,
        team_member_id,
        source,
        accepted_name,
        find_date,
        find_time,
        provisional_identification,
        abund_value,
        notes,
        latitude,
        longitude,
        sync_status,
        created_at_device
      FROM finds_local
      WHERE collection_event_id IN ($placeholders)
        AND (deleted_at_device IS NULL OR TRIM(deleted_at_device) = '')
      ORDER BY datetime(created_at_device) DESC, local_id DESC
      LIMIT ?
      ''',
      <Object?>[...collectionEventIds, limit],
    );
  }

  Future<void> updateFindLocalFields({
    required String localId,
    required int collectionEventId,
    required int teamMemberId,
    required String source,
    required String acceptedName,
    required String findDate,
    required String findTime,
    String? provisionalIdentification,
    String? abundValue,
    String? notes,
    String? latitude,
    String? longitude,
    required String updatedAtDevice,
  }) async {
    final db = await database();
    await db.update(
      'finds_local',
      <String, Object?>{
        'collection_event_id': collectionEventId,
        'team_member_id': teamMemberId,
        'source': source,
        'accepted_name': acceptedName,
        'find_date': findDate,
        'find_time': findTime,
        'provisional_identification': provisionalIdentification,
        'abund_value': abundValue,
        'notes': notes,
        'latitude': latitude,
        'longitude': longitude,
        'updated_at_device': updatedAtDevice,
        'sync_status': 'pending',
        'last_error': null,
      },
      where: 'local_id = ?',
      whereArgs: <Object?>[localId],
    );
  }

  Future<void> updatePendingCreateQueuePayloadForFind({
    required String localId,
    required String payloadJson,
    required String updatedAt,
  }) async {
    final db = await database();
    await db.update(
      'sync_queue',
      <String, Object?>{
        'payload_json': payloadJson,
        'updated_at': updatedAt,
        'next_attempt_at': updatedAt,
      },
      where: 'entity_type = ? AND entity_local_id = ? AND operation = ?',
      whereArgs: <Object?>['find', localId, 'create'],
    );
  }

  Future<void> insertFindPhotoLocal({
    required String localPhotoId,
    required String findLocalId,
    required String filePath,
    required String source,
    required String capturedAtDevice,
    required String createdAtDevice,
    required String updatedAtDevice,
  }) async {
    final db = await database();
    await db.insert('find_photos_local', <String, Object?>{
      'local_photo_id': localPhotoId,
      'find_local_id': findLocalId,
      'file_path': filePath,
      'source': source,
      'captured_at_device': capturedAtDevice,
      'created_at_device': createdAtDevice,
      'updated_at_device': updatedAtDevice,
      'deleted_at_device': null,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<List<Map<String, Object?>>> listFindPhotosByFindLocalId(
    String findLocalId,
  ) async {
    final db = await database();
    return db.query(
      'find_photos_local',
      where:
          "find_local_id = ? AND (deleted_at_device IS NULL OR TRIM(deleted_at_device) = '') AND LOWER(TRIM(source)) != 'placeholder'",
      whereArgs: <Object?>[findLocalId],
      orderBy: 'datetime(captured_at_device) ASC, local_photo_id ASC',
    );
  }

  Future<void> deleteFindPhotoLocal(String localPhotoId) async {
    final db = await database();
    await db.delete(
      'find_photos_local',
      where: 'local_photo_id = ?',
      whereArgs: <Object?>[localPhotoId],
    );
  }

  static Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE trips (
        id INTEGER PRIMARY KEY,
        trip_name TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        location TEXT,
        notes TEXT,
        team TEXT,
        updated_at_server TEXT NOT NULL
      )
      ''');
    await db.execute('''
      CREATE TABLE trip_details_cache (
        trip_id INTEGER PRIMARY KEY,
        payload_json TEXT NOT NULL,
        updated_at_server TEXT NOT NULL
      )
      ''');
    await db.execute('''
      CREATE TABLE finds_local (
        local_id TEXT PRIMARY KEY,
        server_id INTEGER,
        collection_event_id INTEGER NOT NULL,
        team_member_id INTEGER NOT NULL,
        source TEXT NOT NULL,
        accepted_name TEXT NOT NULL,
        find_date TEXT NOT NULL,
        find_time TEXT NOT NULL,
        provisional_identification TEXT,
        abund_value TEXT,
        notes TEXT,
        latitude TEXT,
        longitude TEXT,
        created_at_device TEXT NOT NULL,
        updated_at_device TEXT NOT NULL,
        deleted_at_device TEXT,
        sync_status TEXT NOT NULL CHECK (sync_status IN ('pending', 'syncing', 'synced', 'failed', 'conflict')),
        last_error TEXT
      )
      ''');
    await db.execute('''
      CREATE TABLE sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_local_id TEXT NOT NULL,
        operation TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE,
        payload_json TEXT NOT NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )
      ''');
    await db.execute('''
      CREATE TABLE sync_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
      ''');
    await db.execute('''
      CREATE TABLE find_photos_local (
        local_photo_id TEXT PRIMARY KEY,
        find_local_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        source TEXT NOT NULL,
        captured_at_device TEXT NOT NULL,
        created_at_device TEXT NOT NULL,
        updated_at_device TEXT NOT NULL,
        deleted_at_device TEXT,
        FOREIGN KEY (find_local_id) REFERENCES finds_local(local_id) ON DELETE CASCADE
      )
      ''');
    await db.execute(
      'CREATE INDEX idx_sync_queue_next_attempt_at ON sync_queue(next_attempt_at)',
    );
    await db.execute(
      'CREATE INDEX idx_finds_local_sync_status ON finds_local(sync_status)',
    );
    await db.execute(
      'CREATE INDEX idx_find_photos_local_find_local_id ON find_photos_local(find_local_id)',
    );
  }

  static Future<void> _onUpgrade(
    Database db,
    int oldVersion,
    int newVersion,
  ) async {
    if (oldVersion >= newVersion) {
      return;
    }
    if (oldVersion < 2) {
      await db.execute(
        "ALTER TABLE finds_local ADD COLUMN find_date TEXT NOT NULL DEFAULT ''",
      );
      await db.execute(
        "ALTER TABLE finds_local ADD COLUMN find_time TEXT NOT NULL DEFAULT ''",
      );
      await db.execute("ALTER TABLE finds_local ADD COLUMN latitude TEXT");
      await db.execute("ALTER TABLE finds_local ADD COLUMN longitude TEXT");
    }
    if (oldVersion < 3) {
      await db.execute(
        "ALTER TABLE finds_local ADD COLUMN team_member_id INTEGER NOT NULL DEFAULT 0",
      );
    }
    if (oldVersion < 4) {
      await db.execute('''
      CREATE TABLE IF NOT EXISTS find_photos_local (
        local_photo_id TEXT PRIMARY KEY,
        find_local_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        source TEXT NOT NULL,
        captured_at_device TEXT NOT NULL,
        created_at_device TEXT NOT NULL,
        updated_at_device TEXT NOT NULL,
        deleted_at_device TEXT,
        FOREIGN KEY (find_local_id) REFERENCES finds_local(local_id) ON DELETE CASCADE
      )
      ''');
      await db.execute(
        'CREATE INDEX IF NOT EXISTS idx_find_photos_local_find_local_id ON find_photos_local(find_local_id)',
      );
    }
    if (oldVersion < 5) {
      await db.execute(
        "ALTER TABLE finds_local ADD COLUMN provisional_identification TEXT",
      );
      await db.execute("ALTER TABLE finds_local ADD COLUMN abund_value TEXT");
      await db.execute("ALTER TABLE finds_local ADD COLUMN notes TEXT");
    }
  }
}
