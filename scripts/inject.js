#!/usr/bin/env node
// Reads env vars (from .env.qa or process.env) and injects them into schedule.html.
// Usage: node scripts/inject.js [env-file]   (defaults to .env.qa)
// Output: dist/schedule.html

const fs   = require('fs');
const path = require('path');

const envFile = process.argv[2] || path.join(__dirname, '..', '.env.qa');

// Load env file if it exists (CI uses process.env directly via GitHub secrets)
if (fs.existsSync(envFile)) {
  fs.readFileSync(envFile, 'utf8')
    .split('\n')
    .forEach(line => {
      const [key, ...rest] = line.split('=');
      if (key && rest.length) process.env[key.trim()] = rest.join('=').trim();
    });
}

const required = [
  'FIREBASE_API_KEY',
  'FIREBASE_AUTH_DOMAIN',
  'FIREBASE_PROJECT_ID',
  'FIREBASE_STORAGE_BUCKET',
  'FIREBASE_MESSAGING_SENDER_ID',
  'FIREBASE_APP_ID',
  'ALLOWED_EMAIL',
];

const missing = required.filter(k => !process.env[k] || process.env[k] === 'REPLACE_ME');
if (missing.length) {
  console.error('Missing env vars:', missing.join(', '));
  process.exit(1);
}

fs.mkdirSync(path.join(__dirname, '..', 'dist'), { recursive: true });

for (const file of ['schedule.html', 'index.html', 'portals.html']) {
  const src  = path.join(__dirname, '..', file);
  const dest = path.join(__dirname, '..', 'dist', file);
  let html = fs.readFileSync(src, 'utf8');
  required.forEach(k => { html = html.replaceAll(`__${k}__`, process.env[k]); });
  fs.writeFileSync(dest, html);
  console.log(`Built → ${dest}`);
}
