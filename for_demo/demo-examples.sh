#!/bin/bash


echo "# Here are some examples of lua and eval usage"
echo ""
echo "# Hello world......"
echo ""
echo "# a) run directly with lua"
echo ""
echo "lua hello-world.lua"

echo ""
echo "# b) run (eval) it within the redis lua engine"
echo ""
echo "cat eval-hello-world.sh"
echo ""
echo "./eval-hello-world.sh"
echo ""
echo "# A word on EVAL and --eval"
echo "redis-cli --eval hello-world.lua 0"

echo ""
echo "# c) run (eval) it within the redis lua engine"
echo ""
echo "cat eval-hello-world.sh"
echo ""
echo "./eval-hello-world.sh"


echo ""
echo "# d) using SCRIPT LOAD"
echo ""
echo "redis-cli SCRIPT LOAD \"return 'hello world'\""
echo ""
echo "redis-cli EVALSHA ABC123 0"


echo ""

echo ""
echo "# Add some items to a list"
echo ""
echo "cat eval-list-loop-and-push.sh"
echo ""
echo "./eval-list-loop-and-push.sh"
echo ""


echo ""
echo "# Manipulate some hash value items"
echo ""
echo "cat eval-incr-and-stor.sh"
echo ""
echo "./eval-incr-and-stor.sh"
echo ""



echo ""
echo "# Look for a key name, if you find it then json.decode and return"
echo ""
echo '# redis-cli set account "cat account-info.json"'
echo ""
echo "./eval-json-get-if-exists.sh"
echo ""