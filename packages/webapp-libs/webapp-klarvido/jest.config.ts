export default {
  displayName: 'webapp-klarvido',
  preset: '../../../jest.preset.js',
  transform: {
    '^(?!.*\\.(js|jsx|ts|tsx|css|json)$)': '@nx/react/plugins/jest',
    '^.+\\.[tj]sx?$': ['babel-jest', { presets: ['@nx/react/babel'] }],
  },
  transformIgnorePatterns: ['/node_modules/(?!(@iconify-icons|react-markdown)/)'],
  moduleNameMapper: {
    'react-markdown': '<rootDir>/../webapp-core/src/tests/mocks/reactMarkdown.tsx',
    'remark-gfm': '<rootDir>/../webapp-core/src/tests/mocks/remarkGfm.ts',
  },
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx'],
  setupFilesAfterEnv: ['./src/tests/setupTests.ts'],
  coverageReporters: ['lcov'],
  coveragePathIgnorePatterns: ['/node_modules/', '.*.svg'],
};
