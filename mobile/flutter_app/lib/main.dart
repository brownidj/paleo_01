import 'dart:async';
import 'dart:io';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'src/api/api_client.dart';
import 'src/auth/token_store.dart';
import 'src/data/mobile_data_repository.dart';
import 'src/data/offline_capable_mobile_data_repository.dart';
import 'src/local_db/app_local_database.dart';
import 'src/models/auth_models.dart';
import 'src/models/trip_models.dart';
import 'src/screens/login_screen.dart';
import 'src/screens/trip_detail_screen.dart';
import 'src/screens/trips_screen.dart';

void main() {
  runApp(const PaleoMobileApp());
}

class PaleoMobileApp extends StatefulWidget {
  const PaleoMobileApp({super.key, this.enableSessionRestore = true});

  final bool enableSessionRestore;

  @override
  State<PaleoMobileApp> createState() => _PaleoMobileAppState();
}

class _PaleoMobileAppState extends State<PaleoMobileApp> {
  static const String _configuredApiBaseUrl = String.fromEnvironment(
    'PALEO_API_BASE_URL',
    defaultValue: '',
  );
  static const bool _verifyTls = bool.fromEnvironment(
    'PALEO_API_VERIFY_TLS',
    defaultValue: false,
  );
  static const bool _disableAutoSync = bool.fromEnvironment(
    'PALEO_DISABLE_AUTO_SYNC',
    defaultValue: false,
  );

  late final MobileDataRepository _repository;
  late final String _apiBaseUrl;
  late final TokenStore _tokenStore;
  final Connectivity _connectivity = Connectivity();
  StreamSubscription<List<ConnectivityResult>>? _connectivitySubscription;
  bool _syncInProgress = false;
  bool _isOnline = true;
  String _syncStatusLabel = 'Synced';
  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();
  final GlobalKey<ScaffoldMessengerState> _scaffoldMessengerKey =
      GlobalKey<ScaffoldMessengerState>();

  AuthUser? _currentUser;
  List<TripSummary> _trips = const <TripSummary>[];
  bool _busy = true;
  String? _errorText;

  @override
  void initState() {
    super.initState();
    _apiBaseUrl = _configuredApiBaseUrl.isNotEmpty
        ? _configuredApiBaseUrl
        : _defaultApiBaseUrl();
    _repository = OfflineCapableMobileDataRepository(
      apiClient: ApiClient(baseUrl: _apiBaseUrl, verifyTls: _verifyTls),
      localDatabase: AppLocalDatabase(),
    );
    _tokenStore = TokenStore();
    _wireConnectivitySync();
    _refreshConnectivityState();
    if (!_disableAutoSync) {
      _triggerBackgroundSync();
    }
    if (widget.enableSessionRestore) {
      _restoreSession();
    } else {
      _busy = false;
    }
  }

  String _defaultApiBaseUrl() {
    if (Platform.isAndroid) {
      // Android emulator loopback points to the emulator, not the host machine.
      return 'https://10.0.2.2';
    }
    return 'https://localhost';
  }

  Future<void> _restoreSession() async {
    setState(() {
      _busy = true;
      _errorText = null;
    });
    final access = await _tokenStore.readAccessToken();
    final refresh = await _tokenStore.readRefreshToken();
    if ((access ?? '').isEmpty || (refresh ?? '').isEmpty) {
      setState(() => _busy = false);
      return;
    }
    _repository.setTokens(accessToken: access!, refreshToken: refresh!);
    try {
      final user = await _repository.me();
      final trips = await _repository.listCurrentTrips();
      if (!mounted) {
        return;
      }
      setState(() {
        _isOnline = true;
        _currentUser = user;
        _trips = _sortTripsByStartAscending(trips);
        _busy = false;
      });
      if (!_disableAutoSync) {
        _triggerBackgroundSync();
      }
    } catch (_) {
      await _tokenStore.clear();
      _repository.clearTokens();
      if (!mounted) {
        return;
      }
      setState(() {
        _currentUser = null;
        _trips = const <TripSummary>[];
        _busy = false;
      });
    }
  }

  Future<void> _login({
    required String username,
    required String password,
  }) async {
    setState(() => _errorText = null);
    try {
      final result = await _repository.login(
        username: username,
        password: password,
      );
      await _tokenStore.saveTokens(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
      );
      final user = await _repository.me();
      final trips = await _repository.listCurrentTrips();
      if (!mounted) {
        return;
      }
      setState(() {
        _isOnline = true;
        _currentUser = user;
        _trips = _sortTripsByStartAscending(trips);
        _errorText = null;
      });
      await _refreshSyncStatus();
      if (!_disableAutoSync) {
        _triggerBackgroundSync();
      }
    } on MobileDataRepositoryError catch (exc) {
      if (mounted) {
        setState(() {
          _errorText = exc.message;
          if (_isApiUnreachableMessage(exc.message)) {
            _isOnline = false;
          }
        });
      }
      await _refreshSyncStatus();
    }
  }

  Future<void> _refreshTrips() async {
    try {
      final trips = await _repository.listCurrentTrips();
      if (!mounted) {
        return;
      }
      setState(() {
        _isOnline = true;
        _trips = _sortTripsByStartAscending(trips);
        _errorText = null;
      });
      await _refreshSyncStatus();
    } on MobileDataRepositoryError catch (exc) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorText = exc.message;
        if (_isApiUnreachableMessage(exc.message)) {
          _isOnline = false;
        }
      });
      await _refreshSyncStatus();
    }
  }

  Future<void> _openTrip(TripSummary trip) async {
    try {
      final detail = await _repository.getTripDetail(trip.id);
      final navigator = _navigatorKey.currentState;
      if (!mounted || navigator == null) {
        return;
      }
      setState(() {
        _isOnline = true;
      });
      await _refreshSyncStatus();
      await navigator.push<void>(
        MaterialPageRoute<void>(
          builder: (_) => TripDetailScreen(
            trip: detail,
            defaultTeamMemberId: _currentUser?.teamMemberId ?? 0,
            onCreateFind:
                ({
                  required int collectionEventId,
                  required int teamMemberId,
                  required String findDate,
                  required String findTime,
                  required List<CreateFindPhotoInput> photos,
                  String? provisionalIdentification,
                  String? latitude,
                  String? longitude,
                }) async {
                  await _repository.createFind(
                    collectionEventId: collectionEventId,
                    teamMemberId: teamMemberId,
                    findDate: findDate,
                    findTime: findTime,
                    photos: photos,
                    provisionalIdentification: provisionalIdentification,
                    latitude: latitude,
                    longitude: longitude,
                  );
                  await _refreshSyncStatus();
                  if (!_disableAutoSync) {
                    _triggerBackgroundSync();
                  }
                },
          ),
        ),
      );
    } on MobileDataRepositoryError catch (exc) {
      if (!mounted) {
        return;
      }
      if (_isApiUnreachableMessage(exc.message)) {
        setState(() {
          _isOnline = false;
        });
        await _refreshSyncStatus();
      }
      _scaffoldMessengerKey.currentState?.showSnackBar(
        SnackBar(content: Text(exc.message)),
      );
    }
  }

  Future<void> _logout() async {
    await _tokenStore.clear();
    _repository.clearTokens();
    if (!mounted) {
      return;
    }
    setState(() {
      _currentUser = null;
      _trips = const <TripSummary>[];
      _errorText = null;
    });
  }

  void _wireConnectivitySync() {
    try {
      _connectivitySubscription = _connectivity.onConnectivityChanged.listen((
        List<ConnectivityResult> results,
      ) {
        final online = _hasOnlineConnectivity(results);
        if (mounted) {
          setState(() {
            _isOnline = online;
          });
        } else {
          _isOnline = online;
        }
        _refreshSyncStatus();
        if (_hasOnlineConnectivity(results) && !_disableAutoSync) {
          _triggerBackgroundSync();
        }
      });
    } on MissingPluginException {
      _connectivitySubscription = null;
    }
  }

  bool _hasOnlineConnectivity(List<ConnectivityResult> results) {
    for (final result in results) {
      if (result != ConnectivityResult.none) {
        return true;
      }
    }
    return false;
  }

  void _triggerBackgroundSync() {
    if (_syncInProgress) {
      return;
    }
    if (mounted) {
      setState(() {
        _syncInProgress = true;
      });
    } else {
      _syncInProgress = true;
    }
    _refreshSyncStatus();
    _repository.syncPending().catchError((_) {}).whenComplete(() async {
      if (mounted) {
        setState(() {
          _syncInProgress = false;
        });
      } else {
        _syncInProgress = false;
      }
      await _refreshSyncStatus();
    });
  }

  Future<void> _refreshConnectivityState() async {
    try {
      final results = await _connectivity.checkConnectivity();
      if (!mounted) {
        _isOnline = _hasOnlineConnectivity(results);
        return;
      }
      setState(() {
        _isOnline = _hasOnlineConnectivity(results);
      });
      await _refreshSyncStatus();
    } on MissingPluginException {
      _isOnline = true;
    } catch (_) {
      _isOnline = true;
    }
  }

  Future<void> _refreshSyncStatus() async {
    SyncSnapshot snapshot;
    try {
      snapshot = await _repository.getSyncSnapshot();
    } catch (_) {
      snapshot = const SyncSnapshot(pendingCount: 0, failedCount: 0);
    }
    final nextLabel = resolveSyncStatusLabel(
      isOnline: _isOnline,
      syncInProgress: _syncInProgress,
      pendingCount: snapshot.pendingCount,
      failedCount: snapshot.failedCount,
    );
    if (!mounted) {
      _syncStatusLabel = nextLabel;
      return;
    }
    if (_syncStatusLabel != nextLabel) {
      setState(() {
        _syncStatusLabel = nextLabel;
      });
    }
  }

  @override
  void dispose() {
    _connectivitySubscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Paleo Mobile',
      navigatorKey: _navigatorKey,
      scaffoldMessengerKey: _scaffoldMessengerKey,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1D6F4E)),
      ),
      home: _buildHome(),
    );
  }

  Widget _buildHome() {
    final child = _buildHomeBody();
    return Stack(
      children: [
        child,
        SafeArea(
          child: Align(
            alignment: Alignment.topRight,
            child: Padding(
              padding: const EdgeInsets.only(top: 8, right: 10),
              child: IgnorePointer(
                child: _SyncStatusChip(label: _syncStatusLabel),
              ),
            ),
          ),
        ),
      ],
    );
  }

  bool _isApiUnreachableMessage(String message) {
    final normalized = message.toLowerCase();
    return normalized.contains('cannot reach api');
  }

  List<TripSummary> _sortTripsByStartAscending(List<TripSummary> trips) {
    final sorted = List<TripSummary>.from(trips);
    sorted.sort((a, b) {
      final aDate = _parseDateOnly(a.startDate);
      final bDate = _parseDateOnly(b.startDate);
      if (aDate == null && bDate == null) {
        return a.tripName.toLowerCase().compareTo(b.tripName.toLowerCase());
      }
      if (aDate == null) {
        return 1;
      }
      if (bDate == null) {
        return -1;
      }
      final cmp = aDate.compareTo(bDate);
      if (cmp != 0) {
        return cmp;
      }
      return a.tripName.toLowerCase().compareTo(b.tripName.toLowerCase());
    });
    return sorted;
  }

  DateTime? _parseDateOnly(String? raw) {
    final value = (raw ?? '').trim();
    if (value.isEmpty) {
      return null;
    }
    final dateOnly = value.split('T').first;
    return DateTime.tryParse(dateOnly);
  }

  Widget _buildHomeBody() {
    if (_busy) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_currentUser == null) {
      return LoginScreen(onLogin: _login, errorText: _errorText);
    }
    return TripsScreen(
      trips: _trips,
      loading: false,
      errorText: _errorText,
      onRefresh: _refreshTrips,
      onOpenTrip: _openTrip,
      onLogout: _logout,
    );
  }
}

String resolveSyncStatusLabel({
  required bool isOnline,
  required bool syncInProgress,
  required int pendingCount,
  required int failedCount,
}) {
  if (!isOnline) {
    return 'Offline';
  }
  if (syncInProgress || pendingCount > 0) {
    return 'Syncing';
  }
  if (failedCount > 0) {
    return 'Needs attention';
  }
  return 'Synced';
}

class _SyncStatusChip extends StatelessWidget {
  const _SyncStatusChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final colors = _chipColors(context, label);
    return Material(
      elevation: 2,
      color: colors.$1,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: colors.$2,
          ),
        ),
      ),
    );
  }

  (Color, Color) _chipColors(BuildContext context, String status) {
    final scheme = Theme.of(context).colorScheme;
    switch (status) {
      case 'Offline':
        return (scheme.surfaceContainerHighest, scheme.onSurface);
      case 'Syncing':
        return (scheme.primaryContainer, scheme.onPrimaryContainer);
      case 'Needs attention':
        return (scheme.errorContainer, scheme.onErrorContainer);
      default:
        return (scheme.tertiaryContainer, scheme.onTertiaryContainer);
    }
  }
}
