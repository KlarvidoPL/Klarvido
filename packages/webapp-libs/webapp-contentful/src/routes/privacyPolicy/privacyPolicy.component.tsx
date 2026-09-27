import { privacyPolicyConfig } from '../../components/contentfulContentPage/privacyPolicy.config';
import { StaticContentPage } from '../../components/staticContentPage';
import { privacyPolicyContent } from './privacyPolicy.content';

export const PrivacyPolicy = () => (
  <StaticContentPage
    icon={privacyPolicyConfig.icon}
    title={privacyPolicyConfig.title}
    description={privacyPolicyConfig.description}
    pageTitle={privacyPolicyConfig.pageTitle}
    markdown={privacyPolicyContent}
  />
);
