import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

void main() {
  runApp(const PaleoMobileApp());
}

class PaleoMobileApp extends StatelessWidget {
  const PaleoMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Paleo Mobile',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1D6F4E)),
      ),
      home: const LoginScreen(),
    );
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _username = TextEditingController();
  final TextEditingController _password = TextEditingController();
  final PaleoApi _api = PaleoApi();
  bool _loading = false;
  String? _error;

  Future<void> _submit() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final token = await _api.login(
        username: _username.text.trim(),
        password: _password.text,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => TripsScreen(api: _api, token: token),
        ),
      );
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Paleo Mobile Login')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            TextField(
              controller: _username,
              decoration: const InputDecoration(labelText: 'Username'),
              autocorrect: false,
              enableSuggestions: false,
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
            ),
            TextField(
              controller: _password,
              decoration: const InputDecoration(labelText: 'Password'),
              obscureText: true,
              autocorrect: false,
              enableSuggestions: false,
              smartDashesType: SmartDashesType.disabled,
              smartQuotesType: SmartQuotesType.disabled,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _loading ? null : _submit,
                child: Text(_loading ? 'Signing in...' : 'Sign in'),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Colors.red)),
            ],
          ],
        ),
      ),
    );
  }
}

class TripsScreen extends StatefulWidget {
  const TripsScreen({required this.api, required this.token, super.key});

  final PaleoApi api;
  final String token;

  @override
  State<TripsScreen> createState() => _TripsScreenState();
}

class _TripsScreenState extends State<TripsScreen> {
  late Future<List<TripSummary>> _tripsFuture;

  @override
  void initState() {
    super.initState();
    _tripsFuture = widget.api.fetchTrips(widget.token);
  }

  void _reload() {
    setState(() {
      _tripsFuture = widget.api.fetchTrips(widget.token);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Current Trips'),
        actions: [
          IconButton(onPressed: _reload, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: FutureBuilder<List<TripSummary>>(
        future: _tripsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text('Failed to load trips: ${snapshot.error}'),
              ),
            );
          }
          final trips = snapshot.data ?? <TripSummary>[];
          if (trips.isEmpty) {
            return const Center(child: Text('No current trips available.'));
          }
          return ListView.separated(
            itemCount: trips.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final trip = trips[index];
              return ListTile(
                title: Text(trip.tripName),
                subtitle: const Text('Tap to view trip details'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => TripDetailScreen(
                        api: widget.api,
                        token: widget.token,
                        tripId: trip.id,
                        tripName: trip.tripName,
                      ),
                    ),
                  );
                },
              );
            },
          );
        },
      ),
    );
  }
}

class TripDetailScreen extends StatelessWidget {
  const TripDetailScreen({
    required this.api,
    required this.token,
    required this.tripId,
    required this.tripName,
    super.key,
  });

  final PaleoApi api;
  final String token;
  final int tripId;
  final String tripName;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(tripName)),
      body: FutureBuilder<TripDetail>(
        future: api.fetchTripDetail(token: token, tripId: tripId),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text('Failed to load details: ${snapshot.error}'),
              ),
            );
          }
          final detail = snapshot.data!;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _detailRow('Trip', detail.tripName),
              _detailRow('Start', detail.startDate ?? '-'),
              _detailRow('End', detail.endDate ?? '-'),
              _detailRow('Location', detail.location ?? '-'),
              _detailRow('Team', detail.team ?? '-'),
              _detailRow('Notes', detail.notes ?? '-'),
              if (!detail.canViewDetails)
                const Padding(
                  padding: EdgeInsets.only(top: 12),
                  child: Card(
                    child: ListTile(
                      leading: Icon(Icons.info_outline),
                      title: Text('Limited access'),
                      subtitle: Text(
                        'You are a team member, but not assigned to this trip. '
                        'Detailed fields are hidden.',
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(value),
        ],
      ),
    );
  }
}

class PaleoApi {
  static const String _base = String.fromEnvironment(
    'PALEO_API_BASE_URL',
    defaultValue: 'https://localhost',
  );

  final http.Client _client = IOClient(
    HttpClient()
      ..badCertificateCallback = ((cert, host, port) =>
          host == 'localhost' || host == '127.0.0.1'),
  );

  Uri _uri(String path) => Uri.parse('$_base$path');

  Future<String> login({
    required String username,
    required String password,
  }) async {
    final response = await _client.post(
      _uri('/v1/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    if (response.statusCode != 200) {
      throw Exception(
        'Login failed (${response.statusCode}): ${response.body}',
      );
    }
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    final token = (json['access_token'] as String?) ?? '';
    if (token.isEmpty) {
      throw Exception('Login response missing access token.');
    }
    return token;
  }

  Future<List<TripSummary>> fetchTrips(String token) async {
    final response = await _client.get(
      _uri('/v1/trips'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) {
      throw Exception(
        'Trips request failed (${response.statusCode}): ${response.body}',
      );
    }
    final body = jsonDecode(response.body) as List<dynamic>;
    return body
        .map((item) => TripSummary.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<TripDetail> fetchTripDetail({
    required String token,
    required int tripId,
  }) async {
    final response = await _client.get(
      _uri('/v1/trips/$tripId'),
      headers: {'Authorization': 'Bearer $token'},
    );
    if (response.statusCode != 200) {
      throw Exception(
        'Trip details failed (${response.statusCode}): ${response.body}',
      );
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return TripDetail.fromJson(body);
  }
}

class TripSummary {
  TripSummary({required this.id, required this.tripName});

  final int id;
  final String tripName;

  factory TripSummary.fromJson(Map<String, dynamic> json) {
    return TripSummary(
      id: (json['id'] as num).toInt(),
      tripName: (json['trip_name'] as String?) ?? '',
    );
  }
}

class TripDetail {
  TripDetail({
    required this.id,
    required this.tripName,
    required this.canViewDetails,
    this.startDate,
    this.endDate,
    this.location,
    this.team,
    this.notes,
  });

  final int id;
  final String tripName;
  final String? startDate;
  final String? endDate;
  final String? location;
  final String? team;
  final String? notes;
  final bool canViewDetails;

  factory TripDetail.fromJson(Map<String, dynamic> json) {
    return TripDetail(
      id: (json['id'] as num).toInt(),
      tripName: (json['trip_name'] as String?) ?? '',
      startDate: json['start_date'] as String?,
      endDate: json['end_date'] as String?,
      location: json['location'] as String?,
      team: json['team'] as String?,
      notes: json['notes'] as String?,
      canViewDetails: (json['can_view_details'] as bool?) ?? true,
    );
  }
}
