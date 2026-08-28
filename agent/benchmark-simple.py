#!/usr/bin/env python3

import json
import argparse
import os
import sys
import asyncio
import time
import logging
import random
import string
import redis.asyncio as aioredis
import jwt
from pprint import pformat

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def get_string(length=1024):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))


def intts():
    return int(time.time())


def fake_payload(issuer=None, audience=None):
    import faker
    fake = faker.Faker()
    profile = fake.profile()
    del profile['birthdate']
    del profile['current_location']
    if audience:
        profile['aud'] = audience
    if issuer:
        profile['iss'] = issuer
    return profile


def encode(payload, secret='secret', algorithm='HS256'):
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode(encoded, secret='secret', algorithm='HS256', **kwargs):
    return jwt.decode(encoded, secret, algorithms=[algorithm], **kwargs)


def generate_jwt(extra_args=None):
    extra_args = extra_args or {}
    payload = {'exp': intts() + 3600, **fake_payload(**extra_args)}
    return encode(payload=payload), payload


def delta(name, ts, count, pipeline_size=1):
    te = time.time()
    t = (te - ts) * 1000
    return '%s, %0.2f ms, %d req/s, %d iterations' % (
        name, t, int((count * 1000 / t) * pipeline_size), count
    )


async def connect_redis(host, port):
    return aioredis.Redis(host=host, port=port)


async def rwait_each_command(redis, slen=1024, count=1):
    token, payload = generate_jwt({"audience": "api.alertstack.io"})
    random_text = get_string(slen)
    ts = time.time()
    for _ in range(count):
        await redis.get('foo')
        await redis.incr('bar')
        await redis.set('randomstring', random_text)
        await redis.hset('account:token', 123456, token)
        await redis.hset('account:details', 123456, json.dumps(payload))
        await redis.hget('account:details', 123456)
    log.info(delta("rwait_each_command", ts, count))


async def rpipelined(redis, slen=1024, count=1):
    token, payload = generate_jwt({"audience": "api.alertstack.io"})
    random_text = get_string(slen)
    ts = time.time()
    for _ in range(count):
        await asyncio.gather(
            redis.get('foo'),
            redis.incr('bar'),
            redis.set('randomstring', random_text),
            redis.hset('account:token', 123456, token),
            redis.hset('account:details', 123456, json.dumps(payload)),
            redis.hget('account:details', 123456),
        )
    log.info(delta("rpipelined", ts, count))


async def rexplicit_pipeline(redis, slen=1024, count=1):
    token, payload = generate_jwt({"audience": "api.alertstack.io"})
    random_text = get_string(slen)
    ts = time.time()
    for _ in range(count):
        pipe = redis.pipeline()
        pipe.get('foo')
        pipe.incr('bar')
        pipe.set('randomstring', random_text)
        pipe.hset('account:token', 123456, token)
        pipe.hset('account:details', 123456, json.dumps(payload))
        pipe.hget('account:details', 123456)
        await pipe.execute()
    log.info(delta("rexplicit_pipeline", ts, count))


async def rexplicit_pipeline_p100(redis, slen=1024, count=1, pipeline_size=100):
    token, payload = generate_jwt({"audience": "api.alertstack.io"})
    random_text = get_string(slen)
    ts = time.time()
    for _ in range(count):
        pipe = redis.pipeline()
        for _ in range(pipeline_size):
            pipe.get('foo')
            pipe.incr('bar')
            pipe.set('randomstring', random_text)
            pipe.hset('account:token', 123456, token)
            pipe.hset('account:details', 123456, json.dumps(payload))
            pipe.hget('account:details', 123456)
        await pipe.execute()
    log.info(delta("rexplicit_pipeline_p100", ts, count, pipeline_size))


async def run(host, port, slen=1024, count=1):
    redis = await connect_redis(host, port)
    await rwait_each_command(redis, slen, count)
    await rpipelined(redis, slen, count)
    await rexplicit_pipeline(redis, slen, count)
    await rexplicit_pipeline_p100(redis, slen, count, 100)
    await redis.aclose()


def main():
    ap = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]))
    ap.add_argument("--host", type=str, default="localhost",
                    help="Redis hostname to connect to. Default: localhost")
    ap.add_argument("--port", type=int, default=6379,
                    help="Redis port to connect to. Default: 6379")
    ap.add_argument("--size", type=int, default=1024,
                    help="Payload size in bytes for random strings. Default: 1024")
    ap.add_argument("--count", "-n", type=int, default=1,
                    help="Number of iterations per benchmark. Default: 1")

    args = vars(ap.parse_args())
    asyncio.run(run(args['host'], args['port'], slen=args['size'], count=args['count']))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        log.error(exc)
        sys.exit(1)
