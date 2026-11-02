#!/bin/bash
# wait for the main confirmation runner, then run the extra (semantics/capital) jobs
cd /tmp/claude-1000/-home-dkdlqoddi-012-gemini-soxl-short-hit/e1396d44-d6a0-4721-9e5e-c8d1e2a44cc7/scratchpad/tv
until [ "$(grep -c 'ALL DONE' out/confirm/runner.log)" -ge 1 ] || grep -q CRASH out/confirm/runner.log; do sleep 10; done
echo "main confirm finished: $(tail -1 out/confirm/runner.log | cut -c1-80)"
if grep -q CRASH out/confirm/runner.log; then echo "crashed; not starting extra"; exit 1; fi
sleep 3
printf '%s' 'globalThis.JOBS_FILE = "jobs_extra.json"; return "set";' | curl -s -X POST --data-binary @- http://127.0.0.1:8765/run
./step.sh s_confirm_start.js
until [ "$(grep -c 'ALL DONE' out/confirm/runner.log)" -ge 2 ] || [ "$(grep -c CRASH out/confirm/runner.log)" -ge 1 ]; do sleep 10; done
echo "extra finished: $(tail -1 out/confirm/runner.log | cut -c1-80)"
