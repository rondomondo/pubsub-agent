# pubsub-agent

A **POC** demonstrating Redis PubSub and Redis Keyspace/Keyevent [notifications] using Python's async `redis` library. Includes a benchmarking tool for comparing Redis pipeline strategies.

# Basic Features

- Subscribe to one or more channels and handle incoming messages
- Publish messages to channels (optionally repeat N times)
- Receive Redis keyspace/keyevent notifications
- Generate and validate JWT tokens
- Benchmark sequential vs. pipelined Redis operations

### Tech

| Dependency | Purpose |
|---|---|
| [redis] (>=4.3) | Redis client with built-in asyncio support (`redis.asyncio`) |
| [PyJWT] (>=2.0) | JWT encoding/decoding |
| [Faker] | Fake profile data for JWT payloads |
| [Python 3.9+] | Minimum required Python version |
| [Lua 5.3] | Optional — for server-side Lua scripts |

> **Note:** `aioredis` is no longer used. The modern `redis` package (>=4.3) ships built-in async support via `redis.asyncio`.

### Installation

```sh
git clone <this-repo>
cd pubsub-agent

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cd agent
./pubsub-agent.py --help
```

### Examples — run from the `agent/` directory

##### Help
```sh
./pubsub-agent.py --help
```

##### Subscribe to the default keyspace/keyevent notification channels
```sh
./pubsub-agent.py &
```

##### Enable all Redis notifications on a standalone server
```sh
redis-cli config set notify-keyspace-events KEA
```

##### Set a key that expires in 10 seconds and watch the agent output
```sh
redis-cli set akeyname akeyvalue EX 10
```

##### Publish a message to the default channels 3 times
```sh
./pubsub-agent.py --publish --message "hello world" --count 3
```

##### Subscribe only to `expired` events on Redis database 11
```sh
./pubsub-agent.py --channel '__keyevent@11__:expired' &
redis-cli -n 11 set somekey somevalue ex 10
```

##### Subscribe only to events for a specific key on database 5
```sh
./pubsub-agent.py --channel '__keyspace@5__:somekey' &
redis-cli -n 5 set somekey somevalue
redis-cli -n 5 del somekey
```

##### Generate a JWT token
```sh
./pubsub-agent.py --token
```

##### Validate a JWT token
```sh
./pubsub-agent.py --validate <token>
```

---

### Benchmarking — run from the `agent/` directory

`benchmark-simple.py` compares four async Redis operation strategies across a fixed set of commands (`GET`, `INCR`, `SET`, `HSET`, `HSET`, `HGET`).

| Strategy | Description |
|---|---|
| `rwait_each_command` | Sequential `await` per command — slowest |
| `rpipelined` | Concurrent futures via `asyncio.gather` |
| `rexplicit_pipeline` | Native Redis pipeline |
| `rexplicit_pipeline_p100` | Native pipeline batching 100 command sets — fastest |

```sh
# Run all four benchmarks with 100 iterations and a 2 KB payload
./benchmark-simple.py --count 100 --size 2048
```

```sh
./benchmark-simple.py --help
```

---

### Lua scripts — run from the `lua/` directory

Load Lua scripts into Redis. Note the SHA printed for each script — use it with `EVALSHA`.

```sh
./load-scripts.sh
```

Example using the `codec.lua` script (replace the SHA with the one printed by `load-scripts.sh`):

```sh
redis-cli EVALSHA <sha> 0 json.encode "{'akey':'avalue'}"
redis-cli EVALSHA <sha> 0 json.decode "\"{'akey':'avalue'}\""
```

---

### Troubleshooting

If you see a `ModuleNotFoundError` for `redis`, make sure you have activated the virtualenv:

```sh
source .venv/bin/activate
```

---

License: MIT

   [redis]: <https://github.com/redis/redis-py>
   [PyJWT]: <https://pyjwt.readthedocs.io>
   [Faker]: <https://faker.readthedocs.io>
   [Python 3.9+]: <https://www.python.org>
   [Lua 5.3]: <https://www.lua.org/about.html>
   [notifications]: <https://redis.io/docs/manual/keyspace-notifications/>
