local some_dict = KEYS[1]
local some_key = ARGV[1]

if redis.call("EXISTS", some_dict) == 1 then
  local payload = redis.call("GET", some_dict)
  return cjson.decode(payload)[some_key]
else
  return nil
end
