import type { ComponentContextInput } from '@sb/webapp-api-client/graphql';

export const AI_CONTEXT_EVENT = 'klarvido:attach-context';
export type AiContextAttachment = {
  id: string;
  tenantId: string;
  label: string;
  context: ComponentContextInput;
};

/** Shared entry point for any component that can supply typed, server-resolved context. */
export const askKlarvido = (
  tenantId: string,
  label: string,
  context: ComponentContextInput,
) => {
  const attachment: AiContextAttachment = {
    id: JSON.stringify(context),
    tenantId,
    label,
    context,
  };
  window.dispatchEvent(
    new CustomEvent<AiContextAttachment>(AI_CONTEXT_EVENT, {
      detail: attachment,
    }),
  );
};
