import 'package:flutter/material.dart';

import 'src/api/api_client.dart';
import 'src/auth/token_store.dart';
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
  static const String _apiBaseUrl = String.fromEnvironment(
    'PALEO_API_BASE_URL',
    defaultValue: 'https://localhost',
  );
  static const bool _verifyTls = bool.fromEnvironment(
    'PALEO_API_VERIFY_TLS',
    defaultValue: false,
  );

  late final ApiClient _apiClient;
  late final TokenStore _tokenStore;
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
    _apiClient = ApiClient(baseUrl: _apiBaseUrl, verifyTls: _verifyTls);
    _tokenStore = TokenStore();
    if (widget.enableSessionRestore) {
      _restoreSession();
    } else {
      _busy = false;
    }
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
    _apiClient.setTokens(accessToken: access!, refreshToken: refresh!);
    try {
      final user = await _apiClient.me();
      final trips = await _apiClient.listCurrentTrips();
      if (!mounted) {
        return;
      }
      setState(() {
        _currentUser = user;
        _trips = trips;
        _busy = false;
      });
    } catch (_) {
      await _tokenStore.clear();
      _apiClient.clearTokens();
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
      final result = await _apiClient.login(
        username: username,
        password: password,
      );
      await _tokenStore.saveTokens(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
      );
      final user = await _apiClient.me();
      final trips = await _apiClient.listCurrentTrips();
      if (!mounted) {
        return;
      }
      setState(() {
        _currentUser = user;
        _trips = trips;
        _errorText = null;
      });
    } on ApiClientError catch (exc) {
      setState(() => _errorText = exc.message);
    }
  }

  Future<void> _refreshTrips() async {
    try {
      final trips = await _apiClient.listCurrentTrips();
      if (!mounted) {
        return;
      }
      setState(() {
        _trips = trips;
        _errorText = null;
      });
    } on ApiClientError catch (exc) {
      if (!mounted) {
        return;
      }
      setState(() => _errorText = exc.message);
    }
  }

  Future<void> _openTrip(TripSummary trip) async {
    try {
      final detail = await _apiClient.getTripDetail(trip.id);
      final navigator = _navigatorKey.currentState;
      if (!mounted || navigator == null) {
        return;
      }
      await navigator.push<void>(
        MaterialPageRoute<void>(
          builder: (_) => TripDetailScreen(
            trip: detail,
            onCreateFind:
                ({
                  required int collectionEventId,
                  required String source,
                  required String acceptedName,
                }) => _apiClient.createFind(
                  collectionEventId: collectionEventId,
                  source: source,
                  acceptedName: acceptedName,
                ),
          ),
        ),
      );
    } on ApiClientError catch (exc) {
      if (!mounted) {
        return;
      }
      _scaffoldMessengerKey.currentState?.showSnackBar(
        SnackBar(content: Text(exc.message)),
      );
    }
  }

  Future<void> _logout() async {
    await _tokenStore.clear();
    _apiClient.clearTokens();
    if (!mounted) {
      return;
    }
    setState(() {
      _currentUser = null;
      _trips = const <TripSummary>[];
      _errorText = null;
    });
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
