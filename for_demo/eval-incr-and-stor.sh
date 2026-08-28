#!/bin/sh
echo "Generate a link_id a counter for links visited and store the link"
redis-cli EVAL "$(cat incr-and-stor.lua)" 2 links:counter links:urls 'https://www.alertstack.io/demo/?demoStep=personal'
