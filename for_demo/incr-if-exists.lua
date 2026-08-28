-- if the key exists then increment the value and return it
local key = KEYS[1]

if redis.call("EXISTS", key) == 1 then
    return redis.call("INCR", key)
else
  return nil
end
