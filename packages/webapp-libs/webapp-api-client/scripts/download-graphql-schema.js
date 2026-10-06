const { spawn } = require('child_process');
const fs = require('fs-extra');
const dotenv = require('dotenv');

function runCommand(command, args) {
  return new Promise((resolve, reject) => {
    const cmd = spawn(command, args, { stdio: 'inherit' });

    cmd.on('close', (code) => {
      if (code !== 0) {
        // Arguments may contain CSRF headers; do not include them in errors.
        reject(new Error(`${command} failed with code ${code}`));
      } else {
        resolve();
      }
    });
    cmd.on('error', reject);
  });
}

(async () => {
  try {
    dotenv.config({ path: '../../webapp/.env' });

    const apiUrl = 'http://localhost:5001/api/graphql/';
    // Introspection uses POST, so initialize the same CSRF protection as the app.
    const csrfResponse = await fetch(new URL('../auth/csrf/', apiUrl));
    if (!csrfResponse.ok) throw new Error(`CSRF initialization failed: HTTP ${csrfResponse.status}`);
    const { csrfToken } = await csrfResponse.json();
    if (typeof csrfToken !== 'string' || !csrfToken) throw new Error('Missing CSRF token');
    const cookie = csrfResponse.headers
      .getSetCookie()
      .map((value) => value.split(';')[0])
      .join('; ');
    if (!cookie) throw new Error('Missing CSRF cookie');

    await runCommand('pnpm', [
      'rover',
      'graph',
      'introspect',
      apiUrl,
      '--header',
      `Cookie: ${cookie}`,
      '--header',
      `X-CSRFToken: ${csrfToken}`,
      '--output',
      'graphql/schema/api.graphql',
    ]);

    // Remove obsolete outputs only after a successful download.
    await fs.remove('./src/graphql/__generated/types.ts');
    await fs.remove('./src/graphql/__generated/hooks.ts');
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
})();
