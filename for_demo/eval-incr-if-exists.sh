#!/bin/sh
echo "If the key named by KEYS[1] exists then increment and return it"
redis-cli EVAL "$(cat incr-if-exists.lua)" 1 random:counter
