import { Locale } from '@sb/webapp-core/config/i18n';
import { useIntl } from 'react-intl';

import { termsAndConditionsConfig } from '../../components/contentfulContentPage/contentfulContentPage.config';
import { StaticContentPage } from '../../components/staticContentPage';
import { termsAndConditionsContent } from './termsAndConditions.content';

export const TermsAndConditions = () => {
  const { locale } = useIntl();
  const markdown = termsAndConditionsContent[locale as Locale] ?? termsAndConditionsContent[Locale.ENGLISH]!;

  return (
    <StaticContentPage
      icon={termsAndConditionsConfig.icon}
      title={termsAndConditionsConfig.title}
      description={termsAndConditionsConfig.description}
      pageTitle={termsAndConditionsConfig.pageTitle}
      markdown={markdown}
    />
  );
};
