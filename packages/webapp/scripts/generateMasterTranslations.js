#!/usr/bin/env node
/**
 * Generate Master Translations Script
 *
 * This script runs formatjs extract and then transforms the output
 * into a format suitable for syncing with the backend.
 *
 * The master.json file contains all translation keys with their
 * default messages and descriptions.
 *
 * Usage:
 *   node scripts/generateMasterTranslations.js
 *
 * Output:
 *   packages/webapp-libs/webapp-core/src/translations/master.json
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const OUTPUT_PATH = path.join(__dirname, '../../webapp-libs/webapp-core/src/translations/master.json');

const EN_TRANSLATIONS_PATH = path.join(__dirname, '../../webapp-libs/webapp-core/src/translations/en.json');

function generateMasterTranslations() {
  console.log('🔍 Extracting translations from source files...');
  console.log('');

  const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'klarvido-intl-'));
  const extractedPath = path.join(temporaryDirectory, 'extracted.json');
  try {
    const previousMaster = fs.existsSync(OUTPUT_PATH) ? JSON.parse(fs.readFileSync(OUTPUT_PATH, 'utf8')) : {};
    const previousEnglish = fs.existsSync(EN_TRANSLATIONS_PATH)
      ? JSON.parse(fs.readFileSync(EN_TRANSLATIONS_PATH, 'utf8'))
      : {};
    // Run formatjs extract with extended format to get descriptions
    // Using explicit file patterns to ensure all webapp-libs are included
    // Glob patterns must NOT have extra quotes when shell expansion is used
    // .ts (not just .tsx) is required - intl.formatMessage() calls living in plain
    // hooks files (*.hooks.ts, not components) were being silently skipped, which
    // meant those strings could never be translated for any locale and always fell
    // back to the English defaultMessage in production.
    const sourcePatterns = [
      'src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-ai-assistant/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-core/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-api-client/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-backup/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-contentful/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-crud-demo/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-documents/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-emails/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-finances/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-generative-ai/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-notifications/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-sso/src/**/*.{ts,tsx}',
      '../webapp-libs/webapp-tenants/src/**/*.{ts,tsx}',
    ];

    // formatjs's "**" glob doesn't cross a leading ".." path segment (matched
    // literally by minimatch, not as a wildcard-traversable one), so a single
    // '**/*.d.ts' ignore silently fails to match '../webapp-libs/.../env.d.ts' and
    // formatjs then chokes trying to parse the type-only file. Mirror each source
    // dir's own prefix instead of relying on a leading "**".
    const ignorePatterns = [
      '**/*.spec.tsx',
      '**/*.spec.ts',
      '**/tests/mocks/**',
      ...sourcePatterns.map((p) => p.replace(/\*\*\/\*\.\{ts,tsx\}$/, '**/*.d.ts')),
    ];

    const command = [
      'npx formatjs extract',
      ...sourcePatterns.map((p) => `'${p}'`),
      "--id-interpolation-pattern '[sha512:contenthash:base64:6]'",
      `--out-file '${extractedPath}'`,
      ...ignorePatterns.map((p) => `--ignore '${p}'`),
    ].join(' ');

    execSync(command, {
      cwd: path.join(__dirname, '..'),
      stdio: 'inherit',
      shell: '/bin/bash', // Ensure proper shell with glob expansion
    });

    // Check if the file was created
    if (!fs.existsSync(extractedPath)) {
      throw new Error('Master translations file was not created');
    }

    // Read and count keys
    const extracted = JSON.parse(fs.readFileSync(extractedPath, 'utf8'));
    // Dynamic IDs and manually registered messages cannot all be statically extracted.
    // Remove retired keys explicitly from master.json rather than deleting them here.
    const translations = { ...previousMaster, ...extracted };
    const content = JSON.stringify(translations, null, 2) + '\n';
    fs.writeFileSync(OUTPUT_PATH, content, 'utf8');
    const keyCount = Object.keys(translations).length;

    console.log('');
    console.log('✅ Master translations generated successfully!');
    console.log(`   Output: ${OUTPUT_PATH}`);
    console.log(`   Keys:   ${keyCount}`);
    console.log('');

    // Also update en.json with the same content for bundled fallback
    const english = Object.fromEntries(
      Object.entries(translations).map(([key, message]) => [
        key,
        previousEnglish[key] && previousMaster[key]?.defaultMessage === message.defaultMessage
          ? previousEnglish[key]
          : message,
      ])
    );
    fs.writeFileSync(EN_TRANSLATIONS_PATH, JSON.stringify(english, null, 2) + '\n', 'utf8');
    console.log(`   Also updated: ${EN_TRANSLATIONS_PATH}`);
    console.log('');

    return true;
  } catch (error) {
    console.error('❌ Failed to generate master translations:', error.message);
    process.exitCode = 1;
    return false;
  } finally {
    fs.rmSync(temporaryDirectory, { recursive: true, force: true });
  }
}

generateMasterTranslations();
