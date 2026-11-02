// shared helper: launch headless Chrome with the copied TradingView profile
const path = require('path');
const PW = '/home/dkdlqoddi/.npm/_npx/9833c18b2d85bc59/node_modules/playwright';
const { chromium } = require(PW);
const SP = '/tmp/claude-1000/-home-dkdlqoddi-012-gemini-soxl-short-hit/e1396d44-d6a0-4721-9e5e-c8d1e2a44cc7/scratchpad/tv';
async function launch(opts = {}) {
  const ctx = await chromium.launchPersistentContext(path.join(SP, 'profile'), {
    channel: 'chrome',
    headless: opts.headless !== false,
    viewport: { width: 1680, height: 1000 },
    args: ['--disable-blink-features=AutomationControlled', '--no-first-run', '--no-default-browser-check'],
    ignoreDefaultArgs: ['--enable-automation'],
    acceptDownloads: true,
    permissions: ['clipboard-read', 'clipboard-write'],
  });
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'https://www.tradingview.com' });
  return ctx;
}
module.exports = { launch, SP, chromium };
