import { useMutation } from '@apollo/client/react';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useCurrentTenant } from '@sb/webapp-tenants/providers';

import {
  documentsListCreateMutation,
  documentsListDeleteMutation,
  documentsListQuery,
} from './documents.graphql';

export const useHandleDrop = () => {
  const { data: tenant } = useCurrentTenant();
  const tenantId = tenant?.id ?? '';
  const [commitMutation] = useMutation(documentsListCreateMutation, {
    update(cache, { data }) {
      const node = data?.createDocumentDemoItem?.documentDemoItemEdge?.node;
      if (!node) {
        return;
      }

      const variables = { tenantId };
      const { allDocumentDemoItems } = cache.readQuery({ query: documentsListQuery, variables }) ?? {};
      const isAlreadyInConnection = allDocumentDemoItems?.edges?.some((edge) => edge?.node?.id === node?.id);
      if (isAlreadyInConnection) {
        return;
      }

      cache.updateQuery({ query: documentsListQuery, variables }, (existing) => existing ? {
        ...existing,
        allDocumentDemoItems: {
          ...existing.allDocumentDemoItems,
          edges: [...(existing.allDocumentDemoItems?.edges ?? []), { node }],
        },
      } : existing);
    },
    onCompleted: (data) => {
      trackEvent('document', 'upload', data.createDocumentDemoItem?.documentDemoItemEdge?.node?.id);
    },
  });

  return async (files: File[]) => {
    if (!tenantId) return;
    for (const file of files) {
      await commitMutation({
        variables: {
          input: {
            tenantId,
            file,
          },
        },
      });
    }
  };
};

export const useHandleDelete = () => {
  const { data: tenant } = useCurrentTenant();
  const [commitDeleteMutation] = useMutation(documentsListDeleteMutation, {
    update(cache, { data }) {
      const deletedId = data?.deleteDocumentDemoItem?.deletedIds?.[0];
      const normalizedId = cache.identify({ id: deletedId, __typename: 'DocumentDemoItemType' });
      cache.evict({ id: normalizedId });
    },
    onCompleted: (data) => {
      trackEvent('document', 'delete', data.deleteDocumentDemoItem?.deletedIds?.join(', '));
    },
  });

  return async (id: string) => {
    if (!tenant?.id) return;
    await commitDeleteMutation({
      variables: {
        input: {
          tenantId: tenant.id,
          id,
        },
      },
    });
  };
};
