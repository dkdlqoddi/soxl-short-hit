const lib = process.mainModule.require(SPT + "/tvlib.js");
const fs = process.mainModule.require('fs');
const PLAN = [
  { tf: '15',  bsz: 4000,  start: '2024-11-01T00:00:00-0400' },
  { tf: '60',  bsz: 10000, start: '2024-11-01T00:00:00-0400' },
];
const TOTAL = 44100;
const logf = SPT + "/out/runner_random.log";
const log = (m) => fs.appendFileSync(logf, new Date().toISOString() + ' ' + m + '\n');
globalThis.RUNR = { status: 'running', tf: null, batch: null, done: [], errors: [] };
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  try {
    const base = L.read(SPT + "/pine/screen.pine");
    for (const P of PLAN) {
      RUNR.tf = P.tf;
      const label = await L.setInterval(P.tf);
      log(`tf=${P.tf} chart=${label}`);
      await sleep(3000);
      const nb = Math.ceil(TOTAL / P.bsz);
      for (let b = 0; b < nb; b++) {
        RUNR.batch = b;
        const fp = `${SPT}/out/screen/random_${P.tf}_b${b}.txt`;
        if (fs.existsSync(fp)) { log(`skip existing ${fp}`); continue; }
        let code = base.replace('input.bool(false, "random entries (reference)")', 'input.bool(true, "random entries (reference)")').replace('input.int(0, "batch")', `input.int(${b}, "batch")`).replace('input.int(2000, "batch size"', `input.int(${P.bsz}, "batch size"`)
          .replace('timestamp("2024-11-01T00:00:00-0400"), "start"', `timestamp("${P.start}"), "start"`);
        if (P.mid) code = code.replace('timestamp("2025-11-01T00:00:00-0400"), "mid', `timestamp("${P.mid}"), "mid`);
        let ok = false;
        for (let attempt = 0; attempt < 3 && !ok; attempt++) {
          const t0 = Date.now();
          const ss = await L.setScript(code);
          const r = await L.addOrUpdate(120000);
          if (!r.ok) { log(`tf=${P.tf} b=${b} compile problem: ${JSON.stringify(r).slice(0, 300)}`); await sleep(3000); continue; }
          const hdr = new RegExp('H batch=' + b + ' ');
          let seen = false;
          const t1 = Date.now();
          while (Date.now() - t1 < 180000) { const t = await L.logsText(); if (hdr.test(t)) { seen = true; break; } await sleep(700); }
          if (!seen) { log(`tf=${P.tf} b=${b} attempt ${attempt}: no header within 180s (logs head: ${(await L.logsText()).slice(0, 120).replace(/\n/g, ' ')})`); continue; }
          const computeMs = Date.now() - t1;
          let all = null;
          for (let k = 0; k < 4; k++) {
            all = await lib.readAllLogs(page);
            const lastMsg = all.messages[all.messages.length - 1] || '';
            if (all.contiguous && new RegExp('E batch=' + b + ' done').test(lastMsg) && hdr.test(all.messages[0] || '')) break;
            await sleep(2000);
          }
          const lastMsg = all.messages[all.messages.length - 1] || '';
          const good = all.contiguous && new RegExp('E batch=' + b + ' done').test(lastMsg);
          const nRec = all.messages.filter(m => /\]: R /.test(m)).map(m => (m.split('|').length - 1)).reduce((a, c) => a + c, 0);
          if (good) {
            fs.writeFileSync(fp, all.messages.join('\n'));
            log(`tf=${P.tf} b=${b}/${nb} ok compile=${r.ms}ms compute=${computeMs}ms msgs=${all.count} recs=${nRec} total=${Date.now() - t0}ms`);
            RUNR.done.push(`${P.tf}:${b}`);
            ok = true;
          } else {
            log(`tf=${P.tf} b=${b} attempt ${attempt}: incomplete read (count=${all.count} contiguous=${all.contiguous} last=${lastMsg.slice(0, 60)})`);
          }
        }
        if (!ok) { RUNR.errors.push(`${P.tf}:${b}`); log(`tf=${P.tf} b=${b} FAILED`); }
      }
    }
    RUNR.status = 'finished';
    log('ALL DONE errors=' + JSON.stringify(RUNR.errors));
  } catch (e) {
    RUNR.status = 'crashed: ' + String(e && e.stack || e);
    log('CRASH ' + String(e && e.stack || e));
  }
})();
return 'started';
