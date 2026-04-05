import 'dart:convert';
import 'dart:async';
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
    String? fallbackBaseUrl,
    bool verifyTls = false,
    Duration requestTimeout = const Duration(seconds: 8),
    http.Client? client,
  }) : _baseUrl = baseUrl.replaceFirst(RegExp(r'/+$'), ''),
       _fallbackBaseUrl = (fallbackBaseUrl ?? '')
           .replaceFirst(RegExp(r'/+$'), '')
           .trim(),
       _requestTimeout = requestTimeout,
       _client = client ?? _buildClient(verifyTls: verifyTls);

  final String _baseUrl;
  final String _fallbackBaseUrl;
  final Duration _requestTimeout;
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
    int? teamMemberId,
    required String findDate,
    required String findTime,
    String? latitude,
    String? longitude,
    String? idempotencyKey,
  }) async {
    final headers = <String, String>{};
    if ((idempotencyKey ?? '').isNotEmpty) {
      headers['Idempotency-Key'] = idempotencyKey!;
    }
    final body = <String, dynamic>{
      'collection_event_id': collectionEventId,
      'source': 'Field',
      'accepted_name': 'Unknown',
      'find_date': findDate,
      'find_time': findTime,
      'latitude': latitude,
      'longitude': longitude,
    };
    if ((teamMemberId ?? 0) > 0) {
      body['team_member_id'] = teamMemberId;
    }
    await _request(
      method: 'POST',
      path: '/v1/finds',
      body: body,
      additionalHeaders: headers,
    );
  }

  Future<Map<String, dynamic>> _request({
    required String method,
    required String path,
    Map<String, dynamic>? body,
    bool includeAuth = true,
    bool retried = false,
    bool fallbackTried = false,
    String? baseUrlOverride,
    Map<String, String>? additionalHeaders,
  }) async {
    final effectiveBaseUrl = (baseUrlOverride ?? _baseUrl)
        .replaceFirst(RegExp(r'/+$'), '');
    final uri = Uri.parse('$effectiveBaseUrl$path');
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
    if (additionalHeaders != null && additionalHeaders.isNotEmpty) {
      headers.addAll(additionalHeaders);
    }

    http.Response response;
    try {
      switch (method.toUpperCase()) {
        case 'POST':
          response = await _client
              .post(
                uri,
                headers: headers,
                body: jsonEncode(body ?? const <String, dynamic>{}),
              )
              .timeout(_requestTimeout);
          break;
        case 'GET':
          response = await _client
              .get(uri, headers: headers)
              .timeout(_requestTimeout);
          break;
        default:
          throw ApiClientError('Unsupported HTTP method: $method');
      }
    } on SocketException catch (exc) {
      if (!fallbackTried &&
          _fallbackBaseUrl.isNotEmpty &&
          _fallbackBaseUrl != effectiveBaseUrl) {
        return _request(
          method: method,
          path: path,
          body: body,
          includeAuth: includeAuth,
          retried: retried,
          fallbackTried: true,
          baseUrlOverride: _fallbackBaseUrl,
          additionalHeaders: additionalHeaders,
        );
      }
      throw ApiClientError(
        'Cannot reach API at $effectiveBaseUrl: ${exc.message}',
      );
    } on HandshakeException catch (exc) {
      if (!fallbackTried &&
          _fallbackBaseUrl.isNotEmpty &&
          _fallbackBaseUrl != effectiveBaseUrl) {
        return _request(
          method: method,
          path: path,
          body: body,
          includeAuth: includeAuth,
          retried: retried,
          fallbackTried: true,
          baseUrlOverride: _fallbackBaseUrl,
          additionalHeaders: additionalHeaders,
        );
      }
      throw ApiClientError(
        'Cannot reach API at $effectiveBaseUrl: ${exc.message}',
      );
    } on TimeoutException {
      if (!fallbackTried &&
          _fallbackBaseUrl.isNotEmpty &&
          _fallbackBaseUrl != effectiveBaseUrl) {
        return _request(
          method: method,
          path: path,
          body: body,
          includeAuth: includeAuth,
          retried: retried,
          fallbackTried: true,
          baseUrlOverride: _fallbackBaseUrl,
          additionalHeaders: additionalHeaders,
        );
      }
      throw ApiClientError(
        'Cannot reach API at $effectiveBaseUrl: request timed out after ${_requestTimeout.inSeconds}s',
      );
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
        fallbackTried: fallbackTried,
        baseUrlOverride: effectiveBaseUrl,
        additionalHeaders: additionalHeaders,
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
