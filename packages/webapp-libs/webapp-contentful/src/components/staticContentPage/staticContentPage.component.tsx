import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Paragraph } from '@sb/webapp-core/components/typography';
import { Card, CardContent } from '@sb/webapp-core/components/ui/card';
import { LucideIcon } from 'lucide-react';
import { FC } from 'react';
import { Helmet } from 'react-helmet-async';
import { FormattedMessage, MessageDescriptor, useIntl } from 'react-intl';
import ReactMarkdown from 'react-markdown';

export type StaticContentPageProps = {
  icon: LucideIcon;
  title: MessageDescriptor;
  description: MessageDescriptor;
  pageTitle: MessageDescriptor;
  markdown: string;
};

export const StaticContentPage: FC<StaticContentPageProps> = ({
  icon: Icon,
  title,
  description,
  pageTitle,
  markdown,
}) => {
  const intl = useIntl();

  return (
    <PageLayout>
      <Helmet title={intl.formatMessage(pageTitle)} />
      <div className="mx-auto w-full max-w-4xl space-y-8">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Icon className="h-6 w-6 text-primary" />
            <h1 className="text-3xl font-bold tracking-tight">
              <FormattedMessage {...title} />
            </h1>
          </div>
          <Paragraph className="text-lg text-muted-foreground">
            <FormattedMessage {...description} />
          </Paragraph>
        </div>

        <Card>
          <CardContent className="py-6">
            <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:font-semibold prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-p:text-muted-foreground prose-li:text-muted-foreground prose-a:text-primary">
              <ReactMarkdown>{markdown}</ReactMarkdown>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  );
};
