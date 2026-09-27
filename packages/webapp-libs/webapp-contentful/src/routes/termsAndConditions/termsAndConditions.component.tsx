import { termsAndConditionsConfig } from '../../components/contentfulContentPage/contentfulContentPage.config';
import { StaticContentPage } from '../../components/staticContentPage';
import { termsAndConditionsContent } from './termsAndConditions.content';

export const TermsAndConditions = () => (
  <StaticContentPage
    icon={termsAndConditionsConfig.icon}
    title={termsAndConditionsConfig.title}
    description={termsAndConditionsConfig.description}
    pageTitle={termsAndConditionsConfig.pageTitle}
    markdown={termsAndConditionsContent}
  />
);
