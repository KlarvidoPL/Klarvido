const fs = require('fs-extra');
const os = require('os');
const path = require('path');

const { runCommand } = require('./lib/runCommand');

// Run the container as the calling user (not root) so generated files
// bind-mounted back to the host aren't root-owned - matters on machines
// that reuse a persistent checkout across runs (e.g. self-hosted CI
// runners), where root-owned leftovers block the next `actions/checkout`.
const dockerUserArgs =
  process.platform !== 'win32' && os.userInfo().uid >= 0
    ? ['--user', `${os.userInfo().uid}:${os.userInfo().gid}`]
    : [];

const GENERATED_BACKEND_DOCS_PATH = path.resolve(
  __dirname,
  '../docs/generated',
);
const GENERATED_BACKEND_DOCS_INTERNAL_PATH = path.resolve(
  __dirname,
  '../../internal/docs/docs/api-reference/backend/generated',
);

(async () => {
  try {
    await fs.remove(GENERATED_BACKEND_DOCS_PATH);

    await runCommand(
      'docker',
      [
        'compose',
        'run',
        '--rm',
        '-T',
        '--no-deps',
        ...dockerUserArgs,
        'backend',
        'sh',
        '-c',
        'pydoc-markdown',
      ],
      {
        cwd: path.resolve(__dirname, '../../../'),
      },
    );

    await fs.remove(`${GENERATED_BACKEND_DOCS_INTERNAL_PATH}`);

    await fs.copy(
      GENERATED_BACKEND_DOCS_PATH,
      GENERATED_BACKEND_DOCS_INTERNAL_PATH,
    );
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
})();
