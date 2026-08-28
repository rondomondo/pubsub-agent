-- Do a simple INCRement of the value given by first key KEYS[1]
--
-- redis-cli EVAL "$(cat incr-and-stor.lua)" 2 links:counter links:urls 'https://www.alertstack.io/demo/?demoStep=personal'
--

local link_id = redis.call("INCR", KEYS[1])
-- Set the pointed to link for that id to the value in the second key - use the first argument ARGV[1]
redis.call("HSET", KEYS[2], link_id, ARGV[1])
return link_id
