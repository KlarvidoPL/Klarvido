import { ComponentKind } from '@sb/webapp-api-client/graphql';
import { act, renderHook } from '@testing-library/react';

import { useAiAssistant } from '../hooks/useAiAssistant';

let mockTenantId = 'tenant-1';
let mockSubscriptionData: any;
let mockCounter = 0;
const mockMutation = jest
  .fn()
  .mockResolvedValue({ data: { sendAiMessage: { ok: true } } });
jest.mock('uuid', () => ({ v4: () => `conversation-${++mockCounter}` }));
jest.mock('@sb/webapp-tenants/providers', () => ({
  useCurrentTenant: () => ({ data: { id: mockTenantId } }),
}));
jest.mock('@apollo/client/react', () => ({
  useMutation: () => [mockMutation],
  useSubscription: () => ({ data: mockSubscriptionData }),
}));

it('sends typed context and starts a clean conversation on organization change', async () => {
  const { result, rerender } = renderHook(() => useAiAssistant());
  const context = [
    { kind: ComponentKind.INVOICE_DETAILS, invoiceIds: ['invoice-1'] },
  ];
  await act(async () => {
    await result.current.sendMessage('Question', context);
  });
  const previous = mockMutation.mock.calls[0][0].variables.conversationId;
  expect(mockMutation.mock.calls[0][0].variables.context).toEqual(context);
  expect(result.current.messages).toHaveLength(1);
  mockTenantId = 'tenant-2';
  rerender();
  expect(result.current.messages).toHaveLength(0);
  expect(result.current.isLoading).toBe(false);
  mockSubscriptionData = {
    aiChat: {
      event: {
        eventType: 'content',
        conversationId: previous,
        text: 'previous organization data',
      },
    },
  };
  await act(async () => {
    rerender();
  });
  expect(result.current.messages).toHaveLength(0);
  await act(async () => {
    await result.current.sendMessage('New question');
  });
  expect(mockMutation.mock.calls[1][0].variables.tenantId).toBe('tenant-2');
  expect(mockMutation.mock.calls[1][0].variables.conversationId).not.toBe(
    previous,
  );
  expect(mockMutation.mock.calls[1][0].variables.history).toEqual([]);
});
