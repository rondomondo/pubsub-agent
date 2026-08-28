
-- for count number of times just push the numbers onto a called key
-- to run in redis script engine do,
--
-- So, push a value onto the list called mylist 5 times.
--
-- redis-cli EVAL "$(cat list-loop-and-push.lua)" 1 "mylist" 5
-- note: the 1 just means we have 1 'key' and it's value here is mylist 
--


-- key is the list name
local key = KEYS[1]

-- count is the 
local count = ARGV[1]

for i = 1, count do
    redis.call("LPUSH", key, i)
end

local list_len = redis.call("LLEN", key)
return list_len