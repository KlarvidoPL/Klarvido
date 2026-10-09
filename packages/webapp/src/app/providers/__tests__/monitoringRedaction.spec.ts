import { redactMonitoringData } from '../monitoringRedaction';

describe('authentication monitoring privacy', () => {
  it('removes secrets from structured, serialized, URL and breadcrumb capture', () => {
    const secrets = [
      'private-password',
      'private-seed',
      'private-reset',
      'private-cookie',
      'private-code',
      'private-state',
      'private-oauth',
      'private-basic',
    ];
    const event = {
      request: {
        url: 'https://app.example.com/pl/auth/reset-password/confirm/user/private-reset',
        headers: { Cookie: 'private-cookie' },
        data: JSON.stringify({ password: 'private-password' }),
      },
      extra: {
        serialized: JSON.stringify({ otpBase32: 'private-seed' }),
        enrollment: 'otpauth://totp/app?secret=private-seed',
        url: 'https://api.example.com/callback?code=private-code',
      },
      breadcrumbs: [
        { data: { token: 'private-reset' }, message: 'https://app.example.com/pl/auth/confirm/user/private-reset' },
      ],
      transaction: '/pl/auth/reset-password/confirm/user/private-reset',
      message: 'Useful error without credentials',
      extra_form: 'state=private-state&code=private-oauth',
      extra_url: 'https://user:private-basic@api.example.com/path',
    };
    const result = redactMonitoringData(event);
    for (const secret of secrets) expect(JSON.stringify(result)).not.toContain(secret);
    expect(result.message).toBe(event.message);
    expect(JSON.stringify(event)).toContain('private-password');
  });

  it('redacts encoded URLs and malformed serialized bodies', () => {
    expect(redactMonitoringData('/pl/auth/confirm/user/%70rivate-reset')).not.toContain('private-reset');
    expect(redactMonitoringData('{"password":"private-password"')).toBe('[Filtered]');
  });
});
