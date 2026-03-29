class LoginResult {
  const LoginResult({
    required this.accessToken,
    required this.refreshToken,
  });

  final String accessToken;
  final String refreshToken;

  factory LoginResult.fromJson(Map<String, dynamic> json) {
    return LoginResult(
      accessToken: (json['access_token'] ?? '').toString(),
      refreshToken: (json['refresh_token'] ?? '').toString(),
    );
  }
}

class AuthUser {
  const AuthUser({
    required this.username,
    required this.role,
    required this.displayName,
    required this.teamMemberId,
  });

  final String username;
  final String role;
  final String displayName;
  final int teamMemberId;

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      username: (json['username'] ?? '').toString(),
      role: (json['role'] ?? '').toString(),
      displayName: (json['display_name'] ?? '').toString(),
      teamMemberId: int.tryParse((json['team_member_id'] ?? '').toString()) ?? 0,
    );
  }
}
