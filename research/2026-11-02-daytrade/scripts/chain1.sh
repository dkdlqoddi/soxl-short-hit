#!/bin/bash
# wait for the screening runner, then start the random-reference runner and wait for it
cd /tmp/claude-1000/-home-dkdlqoddi-012-gemini-soxl-short-hit/e1396d44-d6a0-4721-9e5e-c8d1e2a44cc7/scratchpad/tv
until grep -qE "ALL DONE|CRASH" out/runner.log; do sleep 10; done
echo "screening finished: $(tail -1 out/runner.log)"
if grep -q CRASH out/runner.log; then echo "screening crashed, not starting random"; exit 1; fi
sleep 5
./step.sh s_random_start.js
until grep -qE "ALL DONE|CRASH" out/runner_random.log 2>/dev/null; do sleep 10; done
echo "random finished: $(tail -1 out/runner_random.log)"
