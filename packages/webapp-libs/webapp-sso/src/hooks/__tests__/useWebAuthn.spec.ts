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
        expect(await result.current.registerPasskey('Phone')).toBe(true);
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
