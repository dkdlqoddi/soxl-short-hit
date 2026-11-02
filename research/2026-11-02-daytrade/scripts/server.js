// Dev harness: keeps one headless browser alive; POST /run with a JS async-function body
const http = require('http');
const fs = require('fs');
const { launch, SP } = require('./pw.js');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
(async () => {
  const ctx = await launch();
  let page = ctx.pages()[0] || await ctx.newPage();
  page.setDefaultTimeout(30000);
  const h = {
    sleep: ms => new Promise(r => setTimeout(r, ms)),
    shot: async (name, opts = {}) => { await page.screenshot({ path: `${SP}/out/${name}.png`, ...opts }); return `${SP}/out/${name}.png`; },
    aria: async (sel = 'body') => await page.locator(sel).first().ariaSnapshot(),
    paste: async (text) => {
      await page.evaluate(t => navigator.clipboard.writeText(t), text);
      await page.keyboard.press('Control+v');
    },
    log: (...a) => console.log(new Date().toISOString(), ...a),
  };
  const srv = http.createServer((req, res) => {
    if (req.method !== 'POST') { res.writeHead(404); return res.end(); }
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      const t0 = Date.now();
      try {
        const fn = new AsyncFunction('page', 'ctx', 'h', body);
        const out = await fn(page, ctx, h);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, ms: Date.now() - t0, out }, null, 1));
      } catch (e) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, ms: Date.now() - t0, error: String(e && e.stack || e) }, null, 1));
      }
    });
  });
  srv.listen(8765, '127.0.0.1', () => console.log('harness listening on 8765'));
  process.on('SIGTERM', async () => { await ctx.close(); process.exit(0); });
})().catch(e => { console.error('ERR', e); process.exit(1); });
