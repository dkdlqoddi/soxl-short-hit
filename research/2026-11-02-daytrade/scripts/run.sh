#!/bin/bash
# usage: run.sh file.js  |  run.sh -e 'js body'
if [ "$1" = "-e" ]; then printf '%s' "$2" | curl -s -X POST --data-binary @- http://127.0.0.1:8765/run; else curl -s -X POST --data-binary @"$1" http://127.0.0.1:8765/run; fi
echo
