import '../api/api_client.dart';
import '../models/auth_models.dart';
import '../models/trip_models.dart';
import 'mobile_data_repository.dart';

class OnlineMobileDataRepository implements MobileDataRepository {
  OnlineMobileDataRepository({required ApiClient apiClient})
    : _apiClient = apiClient;

  final ApiClient _apiClient;

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
      return await _apiClient.listCurrentTrips();
    } on ApiClientError catch (exc) {
      throw MobileDataRepositoryError(exc.message);
    }
  }

  @override
  Future<TripDetail> getTripDetail(int tripId) async {
    try {
      return await _apiClient.getTripDetail(tripId);
    } on ApiClientError catch (exc) {
      throw MobileDataRepositoryError(exc.message);
    }
  }

  @override
  Future<void> createFind({
    required int collectionEventId,
    required int teamMemberId,
    required String findDate,
    required String findTime,
    String? latitude,
    String? longitude,
  }) async {
    try {
      await _apiClient.createFind(
        collectionEventId: collectionEventId,
        teamMemberId: teamMemberId,
        findDate: findDate,
        findTime: findTime,
        latitude: latitude,
        longitude: longitude,
      );
    } on ApiClientError catch (exc) {
      throw MobileDataRepositoryError(exc.message);
    }
  }

  @override
  Future<void> syncPending() async {}

  @override
  Future<SyncSnapshot> getSyncSnapshot() async {
    return const SyncSnapshot(pendingCount: 0, failedCount: 0);
  }
}
