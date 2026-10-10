import { ApiTestProviders } from '@sb/webapp-api-client/tests/utils/rendering';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { CurrentTenantProvider } from '@sb/webapp-tenants/providers';
import { StoryFn } from '@storybook/react';

import { WrapperProps, getWrapper } from '../tests/utils/rendering';

export function withProviders(wrapperProps: WrapperProps = {}) {
  return (StoryComponent: StoryFn) => {
    const user = currentUserFactory();
    user.tenants = user.tenants?.map((tenant) => ({ ...tenant, id: 'org-1' }));
    const props = {
      ...wrapperProps,
      apolloMocks: typeof wrapperProps.apolloMocks === 'function'
        ? wrapperProps.apolloMocks([fillCommonQueryWithUser(user)])
        : wrapperProps.apolloMocks,
    };
    const { wrapper: WrapperComponent } = getWrapper(ApiTestProviders, props);

    return (
      <WrapperComponent {...wrapperProps}>
        <CurrentTenantProvider>
          <StoryComponent />
        </CurrentTenantProvider>
      </WrapperComponent>
    );
  };
}
