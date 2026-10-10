import { FormattedMessage } from 'react-intl';

import { Layout } from '../../base';

export const Subject = () => (
  <FormattedMessage id="Email / AccountDeleted / Subject" defaultMessage="Your Klarvido account was deleted" />
);
export const Template = () => (
  <Layout
    title={<FormattedMessage id="Email / AccountDeleted / Title" defaultMessage="Account deleted" />}
    text={
      <FormattedMessage
        id="Email / AccountDeleted / Text"
        defaultMessage="Your account has been permanently deleted and its access revoked. Personal file cleanup is being processed. Shared organization content and historical attribution remain. If you did not request this, contact support."
      />
    }
    footer={{ companyName: 'Klarvido' }}
  />
);
