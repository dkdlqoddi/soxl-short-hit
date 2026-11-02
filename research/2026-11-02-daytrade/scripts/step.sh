#!/bin/bash
# usage: step.sh file.js  -> prepends hdr.js (library loader) and posts to the harness
cat /tmp/claude-1000/-home-dkdlqoddi-012-gemini-soxl-short-hit/e1396d44-d6a0-4721-9e5e-c8d1e2a44cc7/scratchpad/tv/hdr.js "$1" | curl -s -X POST --data-binary @- http://127.0.0.1:8765/run; echo
