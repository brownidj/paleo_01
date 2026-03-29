import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

import '../models/auth_models.dart';
import '../models/trip_models.dart';

class ApiClientError implements Exception {
  ApiClientError(this.message);
  final String message;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({
    required String baseUrl,
    bool verifyTls = false,
    http.Client? client,
  }) : _baseUrl = baseUrl.replaceFirst(RegExp(r'/+$'), ''),
       _client = client ?? _buildClient(verifyTls: verifyTls);

  final String _baseUrl;
  final http.Client _client;

  String? _accessToken;
  String? _refreshToken;

  String? get accessToken => _accessToken;
  String? get refreshToken => _refreshToken;

  static http.Client _buildClient({required bool verifyTls}) {
    final raw = HttpClient();
    if (!verifyTls) {
      raw.badCertificateCallback = (certificate, host, port) => true;
    }
    return IOClient(raw);
  }

  void setTokens({required String accessToken, required String refreshToken}) {
    _accessToken = accessToken;
    _refreshToken = refreshToken;
  }

  void clearTokens() {
    _accessToken = null;
    _refreshToken = null;
  }

  Future<LoginResult> login({
    required String username,
    required String password,
  }) async {
    final payload = await _request(
      method: 'POST',
      path: '/v1/auth/login',
      body: <String, dynamic>{'username': username, 'password': password},
      includeAuth: false,
    );
    final result = LoginResult.fromJson(payload);
    if (result.accessToken.isEmpty || result.refreshToken.isEmpty) {
      throw ApiClientError('Login response did not include tokens.');
    }
    setTokens(
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
    );
    return result;
  }

  Future<AuthUser> me() async {
    final payload = await _request(method: 'GET', path: '/v1/auth/me');
    return AuthUser.fromJson(payload);
  }

  Future<List<TripSummary>> listCurrentTrips() async {
    final payload = await _request(method: 'GET', path: '/v1/trips');
    final list = (payload['items'] as List<dynamic>? ?? const <dynamic>[]);
    return list
        .whereType<Map<String, dynamic>>()
        .map(TripSummary.fromJson)
        .toList();
  }

  Future<TripDetail> getTripDetail(int tripId) async {
    final payload = await _request(method: 'GET', path: '/v1/trips/$tripId');
    return TripDetail.fromJson(payload);
  }

  Future<void> createFind({
    required int collectionEventId,
    required String source,
    required String acceptedName,
  }) async {
    await _request(
      method: 'POST',
      path: '/v1/finds',
      body: <String, dynamic>{
        'collection_event_id': collectionEventId,
        'source': source,
        'accepted_name': acceptedName,
      },
    );
  }

  Future<Map<String, dynamic>> _request({
    required String method,
    required String path,
    Map<String, dynamic>? body,
    bool includeAuth = true,
    bool retried = false,
  }) async {
    final uri = Uri.parse('$_baseUrl$path');
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };
    if (includeAuth) {
      if ((_accessToken ?? '').isEmpty) {
        throw ApiClientError('Not authenticated.');
      }
      headers['Authorization'] = 'Bearer $_accessToken';
    }

    http.Response response;
    try {
      switch (method.toUpperCase()) {
        case 'POST':
          response = await _client.post(
            uri,
            headers: headers,
            body: jsonEncode(body ?? const <String, dynamic>{}),
          );
          break;
        case 'GET':
          response = await _client.get(uri, headers: headers);
          break;
        default:
          throw ApiClientError('Unsupported HTTP method: $method');
      }
    } on SocketException catch (exc) {
      throw ApiClientError('Cannot reach API at $_baseUrl: ${exc.message}');
    }

    final text = response.body.trim();
    final decoded = text.isEmpty ? <String, dynamic>{} : _decode(text);

    if (response.statusCode == 401 && includeAuth && !retried) {
      await _refresh();
      return _request(
        method: method,
        path: path,
        body: body,
        includeAuth: includeAuth,
        retried: true,
      );
    }
    if (response.statusCode >= 400) {
      final detail = (decoded['detail'] ?? decoded['message'] ?? text)
          .toString();
      throw ApiClientError(
        '$method $path failed (${response.statusCode}): $detail',
      );
    }
    return decoded;
  }

  Future<void> _refresh() async {
    if ((_refreshToken ?? '').isEmpty) {
      throw ApiClientError('Missing refresh token.');
    }
    final payload = await _request(
      method: 'POST',
      path: '/v1/auth/refresh',
      body: <String, dynamic>{'refresh_token': _refreshToken},
      includeAuth: false,
      retried: true,
    );
    final result = LoginResult.fromJson(payload);
    if (result.accessToken.isEmpty || result.refreshToken.isEmpty) {
      throw ApiClientError('Refresh response did not include tokens.');
    }
    setTokens(
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
    );
  }

  Map<String, dynamic> _decode(String text) {
    final data = jsonDecode(text);
    if (data is Map<String, dynamic>) {
      return data;
    }
    if (data is List<dynamic>) {
      return <String, dynamic>{'items': data};
    }
    return <String, dynamic>{};
  }
}
