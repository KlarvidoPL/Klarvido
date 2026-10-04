import { useMutation, useQuery } from '@apollo/client/react';
import { renderHook } from '@testing-library/react';

import { useTenantKsef } from '../useTenantKsef.hook';

jest.mock('@apollo/client/react', () => ({
  useQuery: jest.fn(),
  useMutation: jest.fn(),
}));

const mockedUseQuery = useQuery as jest.Mock;
const mockedUseMutation = useMutation as jest.Mock;

describe('useTenantKsef', () => {
  const refetch = jest.fn();
  const setMutation = jest.fn();
  // useMutation is called three times in the hook: set, test, delete (in that order)
  let mutationOptions: Array<{ onCompleted?: () => void } | undefined>;

  beforeEach(() => {
    jest.clearAllMocks();
    mutationOptions = [];
    mockedUseQuery.mockReturnValue({
      data: { ksefCredential: { status: 'VALID', tokenName: 'KlarvidoTest' } },
      loading: false,
      error: undefined,
      refetch,
    });
    mockedUseMutation.mockImplementation((_document, options) => {
      mutationOptions.push(options);
      return [setMutation, { loading: false }];
    });
  });

  it('reads the credential metadata for the tenant', () => {
    const { result } = renderHook(() => useTenantKsef('tenant-1', true));

    expect(mockedUseQuery).toHaveBeenCalledWith(expect.anything(), {
      variables: { tenantId: 'tenant-1' },
      skip: false,
    });
    expect(result.current.credential).toEqual({ status: 'VALID', tokenName: 'KlarvidoTest' });
  });

  it('skips the query when there is no tenant or the feature is disabled', () => {
    renderHook(() => useTenantKsef(undefined, true));
    expect(mockedUseQuery).toHaveBeenLastCalledWith(expect.anything(), {
      variables: { tenantId: '' },
      skip: true,
    });

    renderHook(() => useTenantKsef('tenant-1', false));
    expect(mockedUseQuery).toHaveBeenLastCalledWith(expect.anything(), {
      variables: { tenantId: 'tenant-1' },
      skip: true,
    });
  });

  it('returns no credential before the query has data', () => {
    mockedUseQuery.mockReturnValue({ data: undefined, loading: true, error: undefined, refetch });

    const { result } = renderHook(() => useTenantKsef('tenant-1', true));

    expect(result.current.credential).toBeNull();
    expect(result.current.loading).toBe(true);
  });

  it('refetches the credential after a connection test or removal completes', () => {
    renderHook(() => useTenantKsef('tenant-1', true));

    mutationOptions[1]?.onCompleted?.();
    mutationOptions[2]?.onCompleted?.();

    expect(refetch).toHaveBeenCalledTimes(2);
  });

  it('exposes the set, test and delete mutations with their pending states', () => {
    const { result } = renderHook(() => useTenantKsef('tenant-1', true));

    expect(result.current.setToken).toBe(setMutation);
    expect(result.current.testing).toBe(false);
    expect(result.current.deleting).toBe(false);
  });
});
