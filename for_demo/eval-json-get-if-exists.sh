#!/bin/sh
echo "If the key named by KEYS[1] exists then get a sub key identified by ARGV[1]"
echo ""
redis-cli eval "$(cat json-get-if-exists.lua)" 1 account mail
redis-cli eval "$(cat json-get-if-exists.lua)" 1 account company
redis-cli eval "$(cat json-get-if-exists.lua)" 1 account aud
redis-cli eval "$(cat json-get-if-exists.lua)" 1 account exp
