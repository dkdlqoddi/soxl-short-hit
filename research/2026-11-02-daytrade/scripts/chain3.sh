#!/bin/bash
cd /tmp/claude-1000/-home-dkdlqoddi-012-gemini-soxl-short-hit/e1396d44-d6a0-4721-9e5e-c8d1e2a44cc7/scratchpad/tv
until [ "$(grep -c 'ALL DONE' out/confirm/runner.log)" -ge 2 ] || [ "$(grep -c CRASH out/confirm/runner.log)" -ge 2 ]; do sleep 10; done
echo "extra run 1 finished: $(tail -1 out/confirm/runner.log | cut -c1-80)"
for id in $(cat out/confirm/samebar_ids.txt); do rm -f out/confirm/$id.txt; done
echo "deleted sameBar results; restarting runner with hold semantics"
sleep 3
./step.sh s_confirm_start.js
until [ "$(grep -c 'ALL DONE' out/confirm/runner.log)" -ge 3 ] || [ "$(grep -c CRASH out/confirm/runner.log)" -ge 2 ]; do sleep 10; done
echo "extra run 2 finished: $(tail -1 out/confirm/runner.log | cut -c1-80)"
