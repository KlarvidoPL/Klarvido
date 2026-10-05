import { useFragment } from '@apollo/client/react';
import { getFragmentData } from '@sb/webapp-api-client';
import { commonQueryCurrentUserFragment, useCommonQuery } from '@sb/webapp-api-client/providers';

// Subscribe to the normalized profile: the shared network-only query intentionally
// keeps its last server result, whereas a confirmed preference should update now.
export const useCompanyUser = () => {
  const common = useCommonQuery();
  const profile = getFragmentData(commonQueryCurrentUserFragment, common.data?.currentUser);
  const { data } = useFragment({
    fragment: commonQueryCurrentUserFragment,
    fragmentName: 'commonQueryCurrentUserFragment',
    from: profile ? { __typename: 'CurrentUserType', id: profile.id } : null,
  });
  return {
    user: profile
      ? {
          ...profile,
          defaultOrganizationId:
            data.defaultOrganizationId !== undefined ? data.defaultOrganizationId : profile.defaultOrganizationId,
        }
      : profile,
    loading: common.loading,
    error: common.error,
  };
};
