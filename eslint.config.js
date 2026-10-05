const { FlatCompat } = require('@eslint/eslintrc');
const nxEslintPlugin = require('@nx/eslint-plugin');
const js = require('@eslint/js');

const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: js.configs.recommended,
});

module.exports = [
  {
    // Generated files (GraphQL codegen output, etc.) - never lint/fix these. Without this,
    // running `eslint --fix` from the repo root (exactly what lint-staged's pre-commit hook
    // does) resolves this root config instead of the per-package ignore in
    // webapp-api-client/eslint.config.js, and silently strips codegen's own
    // `/* eslint-disable */` header back out on every commit.
    ignores: ['**/__generated/**', '**/__generated__/**'],
  },
  { plugins: { '@nx': nxEslintPlugin } },
  {
    settings: {
      'import/parsers': { '@typescript-eslint/parser': ['.ts', '.tsx'] },
      'import/resolver': {
        typescript: {
          alwaysTryTypes: true,
          project: 'tsconfig.base.json',
        },
      },
    },
  },
  {
    files: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.jsx'],
    rules: {
      '@nx/enforce-module-boundaries': [
        'error',
        {
          enforceBuildableLibDependency: true,
          allow: [
            '@sb/webapp-core/**',
            '@sb/webapp-api-client/**',
            '@sb/webapp-contentful/**',
            '@sb/webapp-crud-demo/**',
            '@sb/webapp-invoices/**',
            '@sb/webapp-ai-assistant/**',
            '@sb/webapp-documents/**',
            '@sb/webapp-finances/**',
            '@sb/webapp-generative-ai/**',
            '@sb/webapp-notifications/**',
            '@sb/webapp-tenants/**',
          ],
          depConstraints: [
            {
              sourceTag: '*',
              onlyDependOnLibsWithTags: ['*'],
            },
          ],
        },
      ],
    },
  },
  ...compat
    .config({
      extends: [
        'plugin:@nx/typescript',
        'prettier',
        'plugin:@typescript-eslint/recommended',
        'plugin:import/errors',
        'plugin:import/warnings',
        'plugin:import/typescript',
      ],
    })
    .map((config) => ({
      ...config,
      files: ['**/*.ts', '**/*.tsx'],
      rules: {},
    })),
  ...compat
    .config({
      extends: [
        'plugin:@nx/javascript',
        'prettier',
        'plugin:import/errors',
        'plugin:import/warnings',
        'plugin:import/typescript',
      ],
    })
    .map((config) => ({
      ...config,
      files: ['**/*.js', '**/*.jsx'],
      rules: {},
    })),
  ...compat.config({ env: { jest: true } }).map((config) => ({
    ...config,
    files: ['**/*.spec.ts', '**/*.spec.tsx', '**/*.spec.js', '**/*.spec.jsx'],
    rules: {},
  })),
  ...compat.config({ parser: 'jsonc-eslint-parser' }).map((config) => ({
    ...config,
    files: ['**/*.json'],
    rules: {},
  })),
];
