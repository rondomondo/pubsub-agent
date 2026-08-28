#!/usr/bin/env python3

import json
import argparse
import os
import sys
import asyncio
import time
import logging
import redis.asyncio as aioredis
import jwt

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

_stop_event = asyncio.Event()


def _fake_payload(issuer=None, audience=None):
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


def _encode_jwt(payload, secret='this secret is over the minimum recommended length of 32 bytes', algorithm='HS256'):
    return jwt.encode(payload, secret, algorithm=algorithm)


def _decode_jwt(encoded, secret='this secret is over the minimum recommended length of 32 bytes', algorithm='HS256', **kwargs):
    return jwt.decode(encoded, secret, algorithms=[algorithm], **kwargs)


def _generate_jwt(extra_args=None):
    extra_args = extra_args or {}
    payload = {'exp': int(time.time()) + 3600, **_fake_payload(**extra_args)}
    return _encode_jwt(payload=payload)


def jwt_token_action(action=None, token_to_check=None):
    if action and action.lower() == "token":
        token = _generate_jwt({"audience": "api.alertstack.io"})
        log.info(token)
        return token

    if action and action.lower() == "validate":
        try:
            result = _decode_jwt(token_to_check, audience="api.alertstack.io")
            log.info(result)
            return result
        except jwt.exceptions.MissingRequiredClaimError as exc:
            log.error(exc)
            return exc
        except Exception as exc:
            log.error(exc)
            return exc


async def receiver(host, port, channel_names):
    client = aioredis.Redis(host=host, port=port)
    sub = client.pubsub()

    async def async_reader(psub):
        async for message in psub.listen():
            if message["type"] not in ("message", "pmessage", "psubscribe", "subscribe"):
                continue
            if message["type"] in ("psubscribe", "subscribe"):
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            channel = message.get("channel", b"")
            if isinstance(channel, bytes):
                channel = channel.decode("utf-8")
            log.info("message received on channel: %s  text: %s  %d bytes", channel, data, len(data))

    await sub.psubscribe(*channel_names)
    for name in channel_names:
        log.info("subscribed to %s", name)

    reader_task = asyncio.create_task(async_reader(sub))

    await _stop_event.wait()

    reader_task.cancel()
    try:
        await reader_task
    except asyncio.CancelledError:
        pass

    await sub.aclose()
    await client.aclose()
    log.info("pubsub end")


async def sender(host, port, channel_names, messages, count=1):
    pub = aioredis.Redis(host=host, port=port)

    for _ in range(count):
        for message in messages:
            for channel_name in channel_names:
                await pub.publish(channel_name, message)

    await pub.aclose()
    log.info("sender end")


def _strip_spaces(data):
    return data.replace(" ", "")


def main():
    ap = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]))

    grouppublish = ap.add_argument_group('publish')

    ap.add_argument("--host", type=str, default="localhost",
                    help="Redis hostname to connect to. Default: localhost")
    ap.add_argument("--port", type=int, default=6379,
                    help="Redis port to connect to. Default: 6379")
    ap.add_argument("--channel", "-c", type=str,
                    default="__keyspace@0__*, __keyevent@0__*",
                    help="Channel(s) to use. Comma-separate for multiple.")
    ap.add_argument("--count", "-n", type=int, default=1,
                    help="Repeat sending the message n times. Default: 1")
    ap.add_argument("--token", action="store_true", default=False,
                    help="Generate a JWT token for testing")
    ap.add_argument("--validate", type=str, default="",
                    help="Validate a JWT token")

    mode_group = ap.add_mutually_exclusive_group()
    mode_group.add_argument("--publish", "-p", action="store_true", default=False,
                            help="Publish a message to the channel(s)")
    mode_group.add_argument("--subscribe", "-s", action="store_true", default=False,
                            help="Subscribe to channel(s) (default behaviour)")

    grouppublish.add_argument("--message", type=str, default="",
                              help="Message to publish when --publish is used")
    grouppublish.add_argument("--notifications", type=str, default="",
                              help="Set Redis notify-keyspace-events (e.g. KEA)")

    args = vars(ap.parse_args())

    host = args['host']
    port = args['port']
    count = args['count']
    channel_names = [c for c in _strip_spaces(args['channel']).split(",") if c]

    if args['token']:
        jwt_token_action(action="token")
        return

    if args['validate']:
        jwt_token_action(action="validate", token_to_check=args['validate'])
        return

    if args['publish']:
        if not args['message']:
            log.error("--publish requires --message")
            sys.exit(1)
        messages = [args['message']]
        asyncio.run(sender(host, port, channel_names, messages, count=count))
    else:
        asyncio.run(receiver(host, port, channel_names))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _stop_event.set()
    except Exception as exc:
        log.error(exc)
        sys.exit(1)
