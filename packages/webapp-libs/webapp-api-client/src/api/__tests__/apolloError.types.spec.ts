import { getGraphQLErrorDetail } from '../apolloError.types';

describe('getGraphQLErrorDetail', () => {
  it('returns undefined when there are no GraphQL errors', () => {
    expect(getGraphQLErrorDetail({})).toBeUndefined();
    expect(getGraphQLErrorDetail({ graphQLErrors: [] })).toBeUndefined();
  });

  it('reads the real detail out of the array-shaped extensions a plain GraphQlValidationError/GraphQlMutationError puts it in, ignoring the useless top-level message', () => {
    const error = {
      graphQLErrors: [
        {
          message: 'GraphQlValidationError',
          extensions: [{ message: 'This role is assigned to 1 member(s). Please provide a replacement role.', code: 'invalid' }],
        },
      ],
    };

    expect(getGraphQLErrorDetail(error)).toBe('This role is assigned to 1 member(s). Please provide a replacement role.');
  });

  it('reads the real detail out of extensions.non_field_errors for serializer-based mutations', () => {
    const error = {
      graphQLErrors: [
        {
          message: 'GraphQlValidationError',
          extensions: { non_field_errors: [{ message: 'Invitation already exists', code: 'invalid' }] },
        },
      ],
    };

    expect(getGraphQLErrorDetail(error)).toBe('Invitation already exists');
  });

  it('uses the top-level message directly when it is real text, e.g. a plain PermissionDenied', () => {
    const error = {
      graphQLErrors: [{ message: 'Only organization owners can assign the Owner role.' }],
    };

    expect(getGraphQLErrorDetail(error)).toBe('Only organization owners can assign the Owner role.');
  });

  it('returns undefined for known placeholder messages with no usable extensions', () => {
    expect(getGraphQLErrorDetail({ graphQLErrors: [{ message: 'GraphQlValidationError' }] })).toBeUndefined();
    expect(getGraphQLErrorDetail({ graphQLErrors: [{ message: 'GraphQlMutationError' }] })).toBeUndefined();
    expect(getGraphQLErrorDetail({ graphQLErrors: [{ message: 'permission_denied' }] })).toBeUndefined();
  });

  it('falls back to `errors` and `result.errors` for Apollo Client 4 error shapes', () => {
    expect(getGraphQLErrorDetail({ errors: [{ message: 'Some error' }] })).toBe('Some error');
    expect(getGraphQLErrorDetail({ result: { errors: [{ message: 'Another error' }] } })).toBe('Another error');
  });
});
