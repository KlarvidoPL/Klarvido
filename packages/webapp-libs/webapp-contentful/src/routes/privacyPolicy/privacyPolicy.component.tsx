import { Locale } from '@sb/webapp-core/config/i18n';
import { useIntl } from 'react-intl';

import { privacyPolicyConfig } from '../../components/contentfulContentPage/privacyPolicy.config';
import { StaticContentPage } from '../../components/staticContentPage';
import { privacyPolicyContent } from './privacyPolicy.content';

export const PrivacyPolicy = () => {
  const { locale } = useIntl();
  const markdown = privacyPolicyContent[locale as Locale] ?? privacyPolicyContent[Locale.ENGLISH]!;

  return (
    <StaticContentPage
      icon={privacyPolicyConfig.icon}
      title={privacyPolicyConfig.title}
      description={privacyPolicyConfig.description}
      pageTitle={privacyPolicyConfig.pageTitle}
      markdown={markdown}
    />
  );
};
