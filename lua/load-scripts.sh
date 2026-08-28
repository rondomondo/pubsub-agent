#!/bin/bash

for i in `ls *.lua`; do 
    echo -n "$i: "; 
    redis-cli  SCRIPT LOAD "`cat $i`"; 
#    redis-cli -h redis-demo-aws.zopim.org  SCRIPT LOAD "`cat $i`"; 
done


echo ""
echo "Now try calling some of the functions we defined in codec.lua"
echo ""
echo "redis-cli EVALSHA a777904787259e4ab40a40a8a7d6d56b53f8b58c 0 ignore.me"
echo ""
echo 'redis-cli EVALSHA a777904787259e4ab40a40a8a7d6d56b53f8b58c 0 json.encode "$(cat messages.json)"'
echo ""
echo 'redis-cli EVALSHA a777904787259e4ab40a40a8a7d6d56b53f8b58c 0 msgpack.encode "$(cat messages.json)"'
echo ""
echo 'redis-cli EVALSHA a777904787259e4ab40a40a8a7d6d56b53f8b58c 0 base64.encode "$(cat messages.json)"'
echo  ""