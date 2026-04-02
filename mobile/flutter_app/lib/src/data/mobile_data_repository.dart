import '../models/auth_models.dart';
import '../models/trip_models.dart';

class MobileDataRepositoryError implements Exception {
  MobileDataRepositoryError(this.message);

  final String message;

  @override
  String toString() => message;
}

class SyncSnapshot {
  const SyncSnapshot({required this.pendingCount, required this.failedCount});

  final int pendingCount;
  final int failedCount;
}

abstract class MobileDataRepository {
  void setTokens({required String accessToken, required String refreshToken});

  void clearTokens();

  Future<LoginResult> login({
    required String username,
    required String password,
  });

  Future<AuthUser> me();

  Future<List<TripSummary>> listCurrentTrips();

  Future<TripDetail> getTripDetail(int tripId);

  Future<void> createFind({
    required int collectionEventId,
    required int teamMemberId,
    required String findDate,
    required String findTime,
    String? latitude,
    String? longitude,
  });

  Future<void> syncPending();

  Future<SyncSnapshot> getSyncSnapshot();
}
