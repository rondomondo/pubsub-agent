import asyncio
import importlib.util
import time
import sys
import unittest
import jwt as pyjwt
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path

# Load module from hyphenated filename
_src = Path(__file__).parent.parent / "agent" / "pubsub-agent.py"
_spec = importlib.util.spec_from_file_location("pubsub_agent", _src)
agent = importlib.util.module_from_spec(_spec)
sys.modules["pubsub_agent"] = agent
_spec.loader.exec_module(agent)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

class TestEncodeDecodeJwt(unittest.TestCase):
    def test_roundtrip(self):
        payload = {"sub": "user1", "exp": int(time.time()) + 60}
        token = agent._encode_jwt(payload)
        decoded = agent._decode_jwt(token)
        self.assertEqual(decoded["sub"], "user1")

    def test_expired_token_raises(self):
        payload = {"sub": "user1", "exp": int(time.time()) - 10}
        token = agent._encode_jwt(payload)
        with self.assertRaises(pyjwt.ExpiredSignatureError):
            agent._decode_jwt(token)

    def test_audience_mismatch_raises(self):
        payload = {"sub": "user1", "exp": int(time.time()) + 60, "aud": "other"}
        token = agent._encode_jwt(payload)
        with self.assertRaises(pyjwt.InvalidAudienceError):
            agent._decode_jwt(token, audience="expected")

    def test_generate_jwt_has_future_exp(self):
        token = agent._generate_jwt()
        decoded = pyjwt.decode(
            token,
            "this secret is over the minimum recommended length of 32 bytes",
            algorithms=["HS256"],
        )
        self.assertGreater(decoded["exp"], int(time.time()))


class TestJwtTokenAction(unittest.TestCase):
    def test_token_action_returns_string(self):
        result = agent.jwt_token_action(action="token")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_validate_action_valid_token(self):
        token = agent._generate_jwt({"audience": "api.alertstack.io"})
        result = agent.jwt_token_action(action="validate", token_to_check=token)
        self.assertIsInstance(result, dict)

    def test_validate_action_bad_token_returns_exception(self):
        result = agent.jwt_token_action(action="validate", token_to_check="not.a.token")
        self.assertIsInstance(result, Exception)

    def test_unknown_action_returns_none(self):
        result = agent.jwt_token_action(action="unknown")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class TestStripSpaces(unittest.TestCase):
    def test_removes_spaces(self):
        self.assertEqual(agent._strip_spaces("a, b, c"), "a,b,c")

    def test_no_spaces(self):
        self.assertEqual(agent._strip_spaces("abc"), "abc")

    def test_empty(self):
        self.assertEqual(agent._strip_spaces(""), "")


# ---------------------------------------------------------------------------
# Sender
# ---------------------------------------------------------------------------

class TestSender(unittest.TestCase):
    def _run(self, coro):
        return run_async(coro)

    def _make_redis(self):
        mock = AsyncMock()
        mock.publish = AsyncMock()
        mock.aclose = AsyncMock()
        return mock

    def test_publishes_to_all_channels(self):
        mock_redis = self._make_redis()
        with patch("pubsub_agent.aioredis.Redis", return_value=mock_redis):
            self._run(agent.sender("localhost", 6379, ["ch1", "ch2"], ["hello"], count=1))
        mock_redis.publish.assert_any_call("ch1", "hello")
        mock_redis.publish.assert_any_call("ch2", "hello")
        self.assertEqual(mock_redis.publish.call_count, 2)

    def test_repeats_count_times(self):
        mock_redis = self._make_redis()
        with patch("pubsub_agent.aioredis.Redis", return_value=mock_redis):
            self._run(agent.sender("localhost", 6379, ["ch1"], ["msg"], count=3))
        self.assertEqual(mock_redis.publish.call_count, 3)

    def test_multiple_messages(self):
        mock_redis = self._make_redis()
        with patch("pubsub_agent.aioredis.Redis", return_value=mock_redis):
            self._run(agent.sender("localhost", 6379, ["ch1"], ["a", "b"], count=1))
        calls = mock_redis.publish.call_args_list
        self.assertIn(call("ch1", "a"), calls)
        self.assertIn(call("ch1", "b"), calls)

    def test_closes_connection(self):
        mock_redis = self._make_redis()
        with patch("pubsub_agent.aioredis.Redis", return_value=mock_redis):
            self._run(agent.sender("localhost", 6379, ["ch"], ["msg"]))
        mock_redis.aclose.assert_called_once()

    def test_no_messages_no_publish(self):
        mock_redis = self._make_redis()
        with patch("pubsub_agent.aioredis.Redis", return_value=mock_redis):
            self._run(agent.sender("localhost", 6379, ["ch"], [], count=1))
        mock_redis.publish.assert_not_called()


# ---------------------------------------------------------------------------
# Receiver
# ---------------------------------------------------------------------------

class TestReceiver(unittest.TestCase):
    def _run(self, coro):
        return run_async(coro)

    def test_subscribes_to_channels(self):
        async def _fake_listen():
            return
            yield  # make it an async generator

        mock_pubsub = MagicMock()
        mock_pubsub.listen = _fake_listen
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.aclose = AsyncMock()

        stop = asyncio.Event()
        orig = agent._stop_event
        agent._stop_event = stop

        async def _run():
            task = asyncio.create_task(agent.receiver("localhost", 6379, ["ch1", "ch2"]))
            await asyncio.sleep(0.05)
            stop.set()
            await task

        try:
            with patch("pubsub_agent.aioredis.Redis", return_value=mock_redis):
                self._run(_run())
        finally:
            agent._stop_event = orig

        mock_pubsub.psubscribe.assert_called_once_with("ch1", "ch2")

    def test_decodes_bytes_message(self):
        logged = []

        async def _fake_listen():
            yield {"type": "pmessage", "data": b"hello", "channel": b"test-ch"}
            # Hang until cancelled
            await asyncio.sleep(10)

        mock_pubsub = MagicMock()
        mock_pubsub.listen = _fake_listen
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.aclose = AsyncMock()

        stop = asyncio.Event()
        orig = agent._stop_event
        agent._stop_event = stop

        async def _run():
            task = asyncio.create_task(agent.receiver("localhost", 6379, ["ch*"]))
            await asyncio.sleep(0.1)
            stop.set()
            await task

        try:
            with patch("pubsub_agent.aioredis.Redis", return_value=mock_redis), \
                 patch.object(agent.log, "info", side_effect=lambda *a, **k: logged.append(a)):
                self._run(_run())
        finally:
            agent._stop_event = orig

        channel_logs = [a for a in logged if "channel" in str(a[0])]
        self.assertTrue(any("hello" in str(a) for a in channel_logs))
        self.assertTrue(any("test-ch" in str(a) for a in channel_logs))

    def test_ignores_non_message_types(self):
        logged = []

        async def _fake_listen():
            yield {"type": "other", "data": b"ignored", "channel": b"ch"}
            await asyncio.sleep(10)

        mock_pubsub = MagicMock()
        mock_pubsub.listen = _fake_listen
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.aclose = AsyncMock()

        stop = asyncio.Event()
        orig = agent._stop_event
        agent._stop_event = stop

        async def _run():
            task = asyncio.create_task(agent.receiver("localhost", 6379, ["ch*"]))
            await asyncio.sleep(0.1)
            stop.set()
            await task

        try:
            with patch("pubsub_agent.aioredis.Redis", return_value=mock_redis), \
                 patch.object(agent.log, "info", side_effect=lambda *a, **k: logged.append(a)):
                self._run(_run())
        finally:
            agent._stop_event = orig

        channel_logs = [a for a in logged if "channel" in str(a[0])]
        self.assertFalse(any("ignored" in str(a) for a in channel_logs))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCli(unittest.TestCase):
    def test_publish_and_subscribe_mutually_exclusive(self):
        sys.argv = ["pubsub-agent.py", "--publish", "--subscribe"]
        with self.assertRaises(SystemExit):
            agent.main()

    def test_publish_without_message_exits(self):
        sys.argv = ["pubsub-agent.py", "--publish"]
        with self.assertRaises(SystemExit):
            agent.main()

    def test_token_flag_calls_jwt_action(self):
        sys.argv = ["pubsub-agent.py", "--token"]
        with patch.object(agent, "jwt_token_action", return_value="tok") as mock_jwt:
            agent.main()
        mock_jwt.assert_called_once_with(action="token")

    def test_validate_flag_calls_jwt_action(self):
        token = agent._generate_jwt({"audience": "api.alertstack.io"})
        sys.argv = ["pubsub-agent.py", "--validate", token]
        with patch.object(agent, "jwt_token_action", return_value={}) as mock_jwt:
            agent.main()
        mock_jwt.assert_called_once_with(action="validate", token_to_check=token)

    def test_subscribe_mode_calls_receiver(self):
        sys.argv = ["pubsub-agent.py", "--subscribe"]
        with patch.object(agent, "receiver", new=AsyncMock()) as mock_recv, \
             patch("pubsub_agent.asyncio.run") as mock_run:
            agent.main()
        mock_run.assert_called_once()

    def test_publish_mode_calls_sender(self):
        sys.argv = ["pubsub-agent.py", "--publish", "--message", "hi"]
        with patch("pubsub_agent.asyncio.run") as mock_run:
            agent.main()
        mock_run.assert_called_once()

    def test_channel_splitting_via_cli(self):
        channels = [c for c in agent._strip_spaces("ch1, ch2, ch3").split(",") if c]
        self.assertEqual(channels, ["ch1", "ch2", "ch3"])


if __name__ == "__main__":
    unittest.main()
