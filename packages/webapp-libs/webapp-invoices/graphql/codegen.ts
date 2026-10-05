import { CodegenConfig } from '@graphql-codegen/cli';

const config: Partial<CodegenConfig> = {
  generates: {
    'src/graphql/__generated/gql/': {
      documents: ['../webapp-invoices/src/**/*.ts', '../webapp-invoices/src/**/*.tsx'],
      plugins: [],
    },
  },
};

export default config;
