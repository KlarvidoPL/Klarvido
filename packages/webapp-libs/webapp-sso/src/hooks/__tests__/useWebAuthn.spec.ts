import { act, renderHook } from '@testing-library/react';
import { csrfFetch } from '@sb/webapp-api-client/api/csrf';
import { useWebAuthn } from '../useWebAuthn';

jest.mock('@sb/webapp-api-client/api/csrf', () => ({ csrfFetch: jest.fn() }));

describe('useWebAuthn', () => {
  it('registers without the optional browser public-key API or a separate publicKey field', async () => {
    const supportDescriptor = Object.getOwnPropertyDescriptor(
      window,
      'PublicKeyCredential',
    );
    const credentialsDescriptor = Object.getOwnPropertyDescriptor(
      navigator,
      'credentials',
    );
    const options = {
      challenge: 'AQID',
      rp: { name: 'Test', id: 'localhost' },
      user: { id: 'AQID', name: 'user@example.com', displayName: 'User' },
      pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
      timeout: 60000,
      attestation: 'none',
      authenticatorSelection: {
        userVerification: 'preferred',
        residentKey: 'required',
        requireResidentKey: true,
      },
      excludeCredentials: [],
    };
    Object.defineProperty(window, 'PublicKeyCredential', {
      configurable: true,
      value: jest.fn(),
    });
    Object.defineProperty(navigator, 'credentials', {
      configurable: true,
      value: {
        create: jest.fn().mockResolvedValue({
          rawId: new Uint8Array([1, 2, 3]).buffer,
          response: {
            attestationObject: new Uint8Array([4, 5, 6]).buffer,
            clientDataJSON: new Uint8Array([7, 8, 9]).buffer,
          },
        }),
      },
    });
    const fetchMock = jest.mocked(csrfFetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => options,
      } as Response)
      .mockResolvedValueOnce({ ok: true } as Response);
    try {
      const { result } = renderHook(() => useWebAuthn());
      await act(async () => {
        expect(
          await result.current.registerPasskey('Phone', 'one-use-proof'),
        ).toBe(true);
      });
      const sent = JSON.parse(fetchMock.mock.calls[1][1]?.body as string);
      expect(sent).toEqual({
        challenge: 'AQID',
        credentialId: 'AQID',
        attestationObject: 'BAUG',
        clientDataJSON: 'BwgJ',
        name: 'Phone',
        transports: [],
      });
      expect(sent).not.toHaveProperty('publicKey');
      for (const [, init] of fetchMock.mock.calls) {
        expect(new Headers(init?.headers).get('X-Passkey-Authorization')).toBe(
          'one-use-proof',
        );
      }
    } finally {
      if (supportDescriptor)
        Object.defineProperty(window, 'PublicKeyCredential', supportDescriptor);
      else Reflect.deleteProperty(window, 'PublicKeyCredential');
      if (credentialsDescriptor)
        Object.defineProperty(navigator, 'credentials', credentialsDescriptor);
      else Reflect.deleteProperty(navigator, 'credentials');
      fetchMock.mockReset();
    }
  });
  it('authorizes a specific deletion with password and OTP', async () => {
    const fetchMock = jest.mocked(csrfFetch);
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ authorization: 'single-use' }),
    } as Response);
    const { result } = renderHook(() => useWebAuthn());
    expect(
      await result.current.authorizePasskeyChange(
        'delete',
        'passkey-id',
        'password',
        '123456',
      ),
    ).toBe('single-use');
    expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toEqual({
      action: 'delete',
      passkeyId: 'passkey-id',
      password: 'password',
      otpToken: '123456',
    });
    fetchMock.mockReset();
  });
  it('does not return authorization when fresh verification fails', async () => {
    const fetchMock = jest.mocked(csrfFetch);
    fetchMock.mockResolvedValueOnce({ ok: false } as Response);
    const { result } = renderHook(() => useWebAuthn());
    await expect(
      result.current.authorizePasskeyChange('register', undefined, 'wrong'),
    ).rejects.toThrow();
    fetchMock.mockReset();
  });
  it('verifies an existing passkey with user verification required before returning proof', async () => {
    const descriptor = Object.getOwnPropertyDescriptor(
      navigator,
      'credentials',
    );
    const get = jest.fn().mockResolvedValue({
      rawId: new Uint8Array([1]).buffer,
      response: {
        authenticatorData: new Uint8Array([2]).buffer,
        clientDataJSON: new Uint8Array([3]).buffer,
        signature: new Uint8Array([4]).buffer,
        userHandle: new Uint8Array([5]).buffer,
      },
    });
    Object.defineProperty(navigator, 'credentials', {
      configurable: true,
      value: { get },
    });
    const fetchMock = jest.mocked(csrfFetch);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          challenge: 'AQ',
          rpId: 'localhost',
          timeout: 60000,
          allowCredentials: [{ id: 'AQ', transports: ['internal'] }],
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authorization: 'single-use' }),
      } as Response);
    try {
      const { result } = renderHook(() => useWebAuthn());
      expect(await result.current.authorizePasskeyChange('register')).toBe(
        'single-use',
      );
      expect(get.mock.calls[0][0].publicKey.userVerification).toBe('required');
      expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toEqual({
        challenge: 'AQ',
        credentialId: 'AQ',
        authenticatorData: 'Ag',
        clientDataJSON: 'Aw',
        signature: 'BA',
        userHandle: 'BQ',
      });
    } finally {
      if (descriptor)
        Object.defineProperty(navigator, 'credentials', descriptor);
      else Reflect.deleteProperty(navigator, 'credentials');
      fetchMock.mockReset();
    }
  });
  describe('isSupported', () => {
    it('should return hook values', () => {
      const { result } = renderHook(() => useWebAuthn());

      expect(result.current).toHaveProperty('isSupported');
      expect(result.current).toHaveProperty('isRegistering');
      expect(result.current).toHaveProperty('isAuthenticating');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('registerPasskey');
      expect(result.current).toHaveProperty('authenticateWithPasskey');
    });

    it('should have registerPasskey as a function', () => {
      const { result } = renderHook(() => useWebAuthn());

      expect(typeof result.current.registerPasskey).toBe('function');
    });

    it('should have authenticateWithPasskey as a function', () => {
      const { result } = renderHook(() => useWebAuthn());

      expect(typeof result.current.authenticateWithPasskey).toBe('function');
    });

    it('should start with no error', () => {
      const { result } = renderHook(() => useWebAuthn());

      expect(result.current.error).toBeNull();
    });

    it('should start with isRegistering as false', () => {
      const { result } = renderHook(() => useWebAuthn());

      expect(result.current.isRegistering).toBe(false);
    });

    it('should start with isAuthenticating as false', () => {
      const { result } = renderHook(() => useWebAuthn());

      expect(result.current.isAuthenticating).toBe(false);
    });
  });
});

it('includes API cookies for both browser-bound login requests', async () => {
  const support = Object.getOwnPropertyDescriptor(
    window,
    'PublicKeyCredential',
  );
  const credentials = Object.getOwnPropertyDescriptor(navigator, 'credentials');
  Object.defineProperty(window, 'PublicKeyCredential', {
    configurable: true,
    value: jest.fn(),
  });
  Object.defineProperty(navigator, 'credentials', {
    configurable: true,
    value: {
      get: jest.fn().mockResolvedValue({
        rawId: new Uint8Array([1]).buffer,
        response: {
          authenticatorData: new Uint8Array([2]).buffer,
          clientDataJSON: new Uint8Array([3]).buffer,
          signature: new Uint8Array([4]).buffer,
          userHandle: new Uint8Array([5]).buffer,
        },
      }),
    },
  });
  const fetchMock = jest.mocked(csrfFetch);
  fetchMock
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        challenge: 'AQ',
        rpId: 'localhost',
        timeout: 60000,
        userVerification: 'required',
      }),
    } as Response)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    } as Response);
  try {
    const { result } = renderHook(() => useWebAuthn());
    await act(async () => {
      expect(await result.current.authenticateWithPasskey()).toEqual({
        success: true,
      });
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toEqual(
      expect.stringContaining('/authenticate/options'),
    );
    expect(fetchMock.mock.calls[1][0]).toEqual(
      expect.stringContaining('/authenticate/verify'),
    );
    for (const [, init] of fetchMock.mock.calls)
      expect(init?.credentials).toBe('include');
  } finally {
    if (support) Object.defineProperty(window, 'PublicKeyCredential', support);
    else Reflect.deleteProperty(window, 'PublicKeyCredential');
    if (credentials)
      Object.defineProperty(navigator, 'credentials', credentials);
    else Reflect.deleteProperty(navigator, 'credentials');
    fetchMock.mockReset();
  }
});

it.each([
  [403, 'incorrect_password'],
  [403, 'incorrect_otp'],
  [403, 'otp_locked'],
  [429, 'rate_limited'],
])('retains a safe reauthentication code for status %s: %s', async (status, code) => {
  const fetchMock = jest.mocked(csrfFetch);
  fetchMock.mockResolvedValueOnce({
    ok: false,
    status,
    json: async () => ({ code, error: 'private server detail' }),
  } as Response);
  const { result } = renderHook(() => useWebAuthn());
  await expect(result.current.authorizePasskeyChange('register', undefined, 'password', '123456'))
    .rejects.toMatchObject({ code, message: 'Fresh authentication failed' });
  fetchMock.mockReset();
});
