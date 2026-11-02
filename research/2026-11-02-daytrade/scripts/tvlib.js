// Reusable TradingView UI helpers for the headless harness (loaded fresh each step)
const fs = require('fs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const ED = '#pine-editor-dialog';
module.exports = (page, h) => {
  const L = {};
  L.closeToasts = async () => {
    const toast = page.locator('div:has(> div:has-text("AI Copilot is now free to try"))').last();
    try { if (await toast.count()) { const x = toast.locator('button, [role=button]').filter({ hasNotText: /Start/ }).first(); if (await x.count()) await x.click({ timeout: 1000 }); } } catch (e) {}
    for (const sel of ['[data-name=toast-group-close-button-charting-ad]', '[data-name=toast-group-close-button-gift]']) {
      const b = page.locator(sel + ':visible');
      const n = await b.count().catch(() => 0);
      for (let i = 0; i < n; i++) await b.nth(i).click({ timeout: 1000 }).catch(() => {});
    }
    const got = page.getByRole('button', { name: 'Got it' });
    if (await got.count()) await got.first().click({ timeout: 1000 }).catch(() => {});
  };
  // console text of the Pine editor (compile messages)
  L.consoleText = async () => page.evaluate(() => { const c = document.querySelector('[class*=console]'); return c ? c.innerText : ''; });
  L.updateBtn = () => page.locator(ED + ' [data-qa-id="add-script-to-chart"]:visible').first();
  L.setScript = async (code) => {
    const ta = page.locator(ED + ' textarea.inputarea').first();
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt === 0) await ta.focus(); else await page.locator(ED + ' .view-lines').first().click({ force: true });
      await sleep(200);
      await page.keyboard.press('Control+a');
      await sleep(100);
      if (attempt < 2) {
        await page.evaluate(t => navigator.clipboard.writeText(t), code);
        await page.keyboard.press('Control+v');
      } else {
        await page.keyboard.press('Delete');
        await page.keyboard.insertText(code);
      }
      await sleep(800);
      // verify: the update/add button must be present and the model's first line must match
      const ok = await L.updateBtn().count();
      if (ok) return { attempt, ok: true };
    }
    return { ok: false };
  };
  // click Add to chart / Update on chart and wait for the console to report the compile result
  L.addOrUpdate = async (timeoutMs = 60000) => {
    const before = (await L.consoleText()).length;
    let btn = L.updateBtn();
    const label = (await btn.getAttribute('title').catch(() => '')) || (await btn.textContent().catch(() => ''));
    if (await btn.isDisabled().catch(() => false)) return { label: 'unchanged', ok: true, ms: 0, tail: 'script identical to the one on the chart; no recompile' };
    await btn.click();
    const t0 = Date.now();
    let tail = '';
    while (Date.now() - t0 < timeoutMs) {
      await sleep(400);
      const txt = await L.consoleText();
      tail = txt.slice(before);
      if (/Error at|error/i.test(tail) && !/Compiling\.\.\.$/.test(tail)) { return { label, ok: false, ms: Date.now() - t0, tail: tail.slice(-800) }; }
      if (/Compiled|Added to chart|Updated on chart|updated|added/i.test(tail)) { return { label, ok: true, ms: Date.now() - t0, tail: tail.slice(-300) }; }
    }
    return { label, ok: null, ms: Date.now() - t0, tail: tail.slice(-800) };
  };
  L.logsText = async () => page.locator('.widgetbar-widget-pine_logs').first().innerText().catch(() => '');
  L.waitLogs = async (re, timeoutMs = 90000) => {
    const t0 = Date.now();
    while (Date.now() - t0 < timeoutMs) {
      const t = await L.logsText();
      if (re.test(t)) return { ms: Date.now() - t0, text: t };
      await sleep(500);
    }
    return { ms: Date.now() - t0, text: await L.logsText(), timeout: true };
  };
  L.setInterval = async (txt) => {
    const ib = page.locator('#header-toolbar-intervals button:visible').first();
    await ib.click();
    await sleep(500);
    await page.keyboard.type(String(txt));
    await sleep(300);
    await page.keyboard.press('Enter');
    await sleep(4000);
    return page.evaluate(() => (document.querySelector('canvas[data-qa-id=pane-top-canvas]') || {}).getAttribute?.('aria-label'));
  };
  L.read = p => fs.readFileSync(p, 'utf8');
  L.write = (p, s) => fs.writeFileSync(p, s);
  return L;
};

// ---- Pine logs: read every message of a virtualized list by scrolling ----
module.exports.readAllLogs = async (page) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const sc = await page.evaluateHandle(() => {
    const w = document.querySelector('.widgetbar-widget-pine_logs');
    const vs = Array.from(w.querySelectorAll('div')).find(e => /virtualScroll/.test(e.className));
    return vs ? vs.parentElement.parentElement : null;
  });
  const msgs = new Map();
  const collect = async () => {
    const arr = await page.evaluate(() => {
      const w = document.querySelector('.widgetbar-widget-pine_logs');
      const vs = Array.from(w.querySelectorAll('div')).find(e => /virtualScroll/.test(e.className));
      if (!vs) return [];
      return Array.from(vs.querySelectorAll('[data-index]')).map(e => [parseInt(e.getAttribute('data-index')), e.innerText]);
    });
    for (const [i, t] of arr) msgs.set(i, t);
  };
  await page.evaluate(sc => { sc.scrollTop = 0; }, sc);
  await sleep(200);
  let last = -1;
  for (let i = 0; i < 5000; i++) {
    await collect();
    const pos = await page.evaluate(sc => { const before = sc.scrollTop; sc.scrollTop = before + Math.floor(sc.clientHeight * 0.85); return [before, sc.scrollTop]; }, sc);
    if (pos[1] === pos[0]) break;
    await sleep(100);
  }
  await collect();
  const idx = Array.from(msgs.keys()).sort((a, b) => a - b);
  return { count: idx.length, maxIndex: idx.length ? idx[idx.length - 1] : -1, contiguous: idx.every((v, j) => v === j), messages: idx.map(i => msgs.get(i)) };
};
