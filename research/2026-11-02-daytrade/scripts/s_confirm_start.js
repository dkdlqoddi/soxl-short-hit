// Strategy Tester confirmation runner: jobs from out/confirm/jobs.json -> out/confirm/<id>.txt (Pine Logs of the strategy script)
// job: { id, tf, buyA, buyB, sellA, sellB, params: { tpPct, slPct, trPct, chMult, holdHrs, maxHrs } }
const lib = process.mainModule.require(SPT + "/tvlib.js");
const fs = process.mainModule.require('fs');
const jobs = JSON.parse(fs.readFileSync(SPT + "/out/confirm/" + (globalThis.JOBS_FILE || "jobs.json"), 'utf8'));
const logf = SPT + "/out/confirm/runner.log";
const log = (m) => fs.appendFileSync(logf, new Date().toISOString() + ' ' + m + '\n');
globalThis.CONF = { status: 'running', job: null, done: 0, errors: [] };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const DEF = { tpPct: 3.0, slPct: 2.0, trPct: 2.0, chMult: 2.0, holdHrs: 4.0, maxHrs: 24.0 };
(async () => {
  try {
    const base = L.read(SPT + "/pine/strategy.pine");
    let curTf = null;
    for (const J of jobs) {
      CONF.job = J.id;
      const fp = `${SPT}/out/confirm/${J.id}.txt`;
      if (fs.existsSync(fp)) { CONF.done++; continue; }
      if (J.tf !== curTf) { const label = await L.setInterval(J.tf); log(`tf=${J.tf} chart=${label}`); curTf = J.tf; await sleep(2500); }
      const P = Object.assign({}, DEF, J.params || {});
      let code = base
        .replace('input.int(16, "buy A (0-19)"', `input.int(${J.buyA}, "buy A (0-19)"`)
        .replace('input.int(-1, "buy B (-1 none)"', `input.int(${J.buyB}, "buy B (-1 none)"`)
        .replace('input.int(14, "sell A (0-19)"', `input.int(${J.sellA}, "sell A (0-19)"`)
        .replace('input.int(-1, "sell B (-1 none)"', `input.int(${J.sellB}, "sell B (-1 none)"`)
        .replace('input.int(0, "run id (log marker)")', `input.int(${J.id}, "run id (log marker)")`)
        .replace('input.float(3.0, "take profit %")', `input.float(${P.tpPct}, "take profit %")`)
        .replace('input.float(2.0, "stop loss %")', `input.float(${P.slPct}, "stop loss %")`)
        .replace('input.float(2.0, "trailing stop %")', `input.float(${P.trPct}, "trailing stop %")`)
        .replace('input.float(2.0, "chandelier ATR mult")', `input.float(${P.chMult}, "chandelier ATR mult")`)
        .replace('input.float(4.0, "time exit hours")', `input.float(${P.holdHrs}, "time exit hours")`)
        .replace('input.float(24.0, "max hold hours")', `input.float(${P.maxHrs}, "max hold hours")`);
      if (J.start) code = code.replace('timestamp("2024-11-01T00:00:00-0400"), "start"', `timestamp("${J.start}"), "start"`);
      if (P.capital) code = code.replace('initial_capital=8200,', `initial_capital=${P.capital},`);
      if (P.sameBar) code = code.replace('input.bool(false, "allow re-entry on the exit bar (screening semantics)")', 'input.bool(true, "allow re-entry on the exit bar (screening semantics)")');
      let ok = false;
      for (let attempt = 0; attempt < 3 && !ok; attempt++) {
        const t0 = Date.now();
        let r;
        try { await L.setScript(code); r = await L.addOrUpdate(120000); }
        catch (e) { log(`job ${J.id} attempt ${attempt} exception: ${String(e).slice(0, 200)}`); await sleep(3000); continue; }
        if (!r.ok) { log(`job ${J.id} compile problem: ${JSON.stringify(r).slice(0, 400)}`); await sleep(2000); continue; }
        const idRe = String(J.id).replace(/\B(?=(\d{3})+(?!\d))/g, ',?');  // Pine prints {0} with thousands separators
        const endRe = new RegExp('E run=' + idRe + ' done');
        const bRe = new RegExp('B run=' + idRe + ' ');
        let seen = false;
        const t1 = Date.now();
        while (Date.now() - t1 < 120000) { const t = await L.logsText(); if (bRe.test(t)) { seen = true; break; } await sleep(500); }
        if (!seen) { log(`job ${J.id} attempt ${attempt}: no S/E line within 120s`); continue; }
        await sleep(1500);
        let all = null;
        for (let k = 0; k < 4; k++) {
          all = await lib.readAllLogs(page);
          if (all.contiguous && endRe.test(all.messages[all.messages.length - 1] || '')) break;
          await sleep(1500);
        }
        if (all.contiguous && endRe.test(all.messages[all.messages.length - 1] || '')) {
          // also scrape the Strategy Tester key stats for a cross-check
          const key = await page.evaluate(() => { const b = document.querySelector('#bottom-area'); if (!b) return null; const t = b.innerText; const i = t.indexOf('Key stats'); return i >= 0 ? t.slice(i, i + 400).replace(/\n/g, ' / ') : t.slice(0, 300).replace(/\n/g, ' / '); });
          fs.writeFileSync(fp, all.messages.join('\n') + '\nKEYSTATS ' + (key || '') + '\n');
          log(`job ${J.id} ok tf=${J.tf} b=${J.buyA}/${J.buyB} s=${J.sellA}/${J.sellB} msgs=${all.count} ${Date.now() - t0}ms key=${(key || '').slice(0, 160)}`);
          ok = true; CONF.done++;
        } else {
          log(`job ${J.id} attempt ${attempt}: incomplete read count=${all.count} contiguous=${all.contiguous}`);
        }
      }
      if (!ok) { CONF.errors.push(J.id); log(`job ${J.id} FAILED`); }
    }
    CONF.status = 'finished';
    log('ALL DONE errors=' + JSON.stringify(CONF.errors));
  } catch (e) {
    CONF.status = 'crashed: ' + String(e && e.stack || e);
    log('CRASH ' + String(e && e.stack || e));
  }
})();
return 'started ' + jobs.length + ' jobs';
