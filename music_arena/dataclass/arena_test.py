import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from ..audio import Audio
from ..dataclass.arena import (
    Battle,
    ListenEvent,
    Preference,
    ResponseMetadata,
    Session,
    User,
    Vote,
)
from ..dataclass.prompt import DetailedTextToMusicPrompt, SimpleTextToMusicPrompt
from ..dataclass.system_metadata import SystemKey
from ..helper import checksum, salted_checksum


class TestPreference(unittest.TestCase):
    def test_preference_enum_values(self):
        self.assertEqual(Preference.A.value, "A")
        self.assertEqual(Preference.B.value, "B")
        self.assertEqual(Preference.TIE.value, "TIE")
        self.assertEqual(Preference.BOTH_BAD.value, "BOTH_BAD")


class TestListenEvent(unittest.TestCase):
    def test_listen_event_enum_values(self):
        self.assertEqual(ListenEvent.PLAY.value, "PLAY")
        self.assertEqual(ListenEvent.PAUSE.value, "PAUSE")


class TestSession(unittest.TestCase):
    def test_session_initialization_empty(self):
        session = Session()
        self.assertIsNotNone(session.uuid)
        self.assertIsNotNone(session.create_time)
        self.assertIsNone(session.frontend_git_hash)
        self.assertIsNone(session.ack_tos)
        self.assertEqual(session.new_battle_times, [])

    def test_session_uuid_uniqueness(self):
        session1 = Session()
        session2 = Session()
        self.assertNotEqual(session1.uuid, session2.uuid)

    def test_session_from_dict(self):
        d = {
            "uuid": "test-uuid",
            "ack_tos": "test-ack-tos",
            "new_battle_times": [123.456, 789.012],
        }
        session = Session.from_dict(d)
        self.assertEqual(session.uuid, "test-uuid")
        self.assertEqual(session.ack_tos, "test-ack-tos")
        self.assertEqual(session.new_battle_times, [123.456, 789.012])


class TestUser(unittest.TestCase):
    @patch("music_arena.dataclass.arena.get_secret")
    def test_user_initialization_empty(self, mock_get_secret):
        mock_get_secret.return_value = "test-salt"
        user = User()
        self.assertIsNone(user.ip)
        self.assertIsNone(user.salted_ip)
        self.assertIsNone(user.fingerprint)
        self.assertIsNone(user.salted_fingerprint)

    @patch("music_arena.dataclass.arena.get_secret")
    def test_user_ip_anonymization(self, mock_get_secret):
        mock_get_secret.return_value = "test-salt"
        user = User(ip="192.168.1.1")
        self.assertIsNone(user.ip)
        self.assertIsNotNone(user.salted_ip)
        self.assertEqual(user.salted_ip, salted_checksum("192.168.1.1", "test-salt"))
        self.assertEqual(user.salted_ip, "3d7c16a221ce6d8f265dc2b679bb3bb4")
        self.assertEqual(
            salted_checksum("192.168.1.1", "test-salt"),
            "3d7c16a221ce6d8f265dc2b679bb3bb4",
        )
        self.assertNotEqual(user.salted_ip, checksum("192.168.1.1"))
        self.assertNotEqual(
            user.salted_ip, salted_checksum("192.168.1.1", "test-salt-2")
        )

    @patch("music_arena.dataclass.arena.get_secret")
    def test_user_fingerprint_anonymization(self, mock_get_secret):
        mock_get_secret.return_value = "test-salt"
        user = User(fingerprint="test-fingerprint")
        self.assertIsNone(user.fingerprint)
        self.assertIsNotNone(user.salted_fingerprint)
        self.assertEqual(
            user.salted_fingerprint, salted_checksum("test-fingerprint", "test-salt")
        )

    @patch("music_arena.dataclass.arena.get_secret")
    def test_user_both_anonymization(self, mock_get_secret):
        mock_get_secret.return_value = "test-salt"
        user = User(ip="192.168.1.1", fingerprint="test-fingerprint")
        self.assertIsNone(user.ip)
        self.assertIsNone(user.fingerprint)
        self.assertIsNotNone(user.salted_ip)
        self.assertIsNotNone(user.salted_fingerprint)

    @patch("music_arena.dataclass.arena.get_secret")
    def test_user_checksum_consistency(self, mock_get_secret):
        mock_get_secret.return_value = "test-salt"
        user1 = User(ip="192.168.1.1", fingerprint="test-fingerprint")
        user2 = User(ip="192.168.1.1", fingerprint="test-fingerprint")

        self.assertEqual(user1.checksum, user2.checksum)

    @patch("music_arena.dataclass.arena.get_secret")
    def test_user_checksum_different_data(self, mock_get_secret):
        mock_get_secret.return_value = "test-salt"
        user1 = User(ip="192.168.1.1")
        user2 = User(ip="192.168.1.2")

        self.assertNotEqual(user1.checksum, user2.checksum)

    @patch("music_arena.dataclass.arena.get_secret")
    def test_user_checksum_with_none_values(self, mock_get_secret):
        mock_get_secret.return_value = "test-salt"
        user = User()
        checksum = user.checksum
        self.assertIsInstance(checksum, str)
        self.assertEqual(len(checksum), 32)  # MD5 hash length

    @patch("music_arena.dataclass.arena.get_secret")
    def test_from_dict(self, mock_get_secret):
        mock_get_secret.return_value = "test-salt"
        d = {
            "salted_ip": "test-salted-ip",
            "salted_fingerprint": "test-salted-fingerprint",
        }
        user = User.from_dict(d)
        self.assertEqual(user.salted_ip, "test-salted-ip")
        self.assertEqual(user.salted_fingerprint, "test-salted-fingerprint")
        d = {
            "ip": "192.168.1.1",
            "fingerprint": "test-fingerprint",
        }
        user = User.from_dict(d)
        self.assertIsNone(user.ip)
        self.assertIsNone(user.fingerprint)
        self.assertIsNotNone(user.salted_ip)
        self.assertIsNotNone(user.salted_fingerprint)


class TestVote(unittest.TestCase):
    def test_vote_initialization(self):
        vote = Vote()
        self.assertEqual(vote.a_listen_data, [])
        self.assertEqual(vote.b_listen_data, [])
        self.assertIsNone(vote.preference)
        self.assertIsNone(vote.preference_time)
        self.assertIsNone(vote.a_feedback)
        self.assertIsNone(vote.b_feedback)

    def test_preference_sets_time(self):
        vote = Vote()
        self.assertIsNone(vote.preference_time)

        start_time = time.time()
        vote.preference = Preference.A
        end_time = time.time()

        self.assertEqual(vote.preference, Preference.A)
        self.assertIsNotNone(vote.preference_time)
        self.assertGreaterEqual(vote.preference_time, start_time)
        self.assertLessEqual(vote.preference_time, end_time)

    def test_preference_time_not_overwritten(self):
        vote = Vote()
        vote.preference = Preference.A
        original_time = vote.preference_time

        vote.preference = Preference.B
        self.assertEqual(vote.preference, Preference.B)
        self.assertEqual(vote.preference_time, original_time)

    def test_play_method(self):
        vote = Vote()

        start_time = time.time()
        vote.play("a")
        end_time = time.time()

        self.assertEqual(len(vote.a_listen_data), 1)
        self.assertEqual(vote.a_listen_data[0][0], ListenEvent.PLAY)
        self.assertGreaterEqual(vote.a_listen_data[0][1], start_time)
        self.assertLessEqual(vote.a_listen_data[0][1], end_time)

        vote.play("b")
        self.assertEqual(len(vote.b_listen_data), 1)
        self.assertEqual(vote.b_listen_data[0][0], ListenEvent.PLAY)

    def test_pause_method(self):
        vote = Vote()

        start_time = time.time()
        vote.pause("a")
        end_time = time.time()

        self.assertEqual(len(vote.a_listen_data), 1)
        self.assertEqual(vote.a_listen_data[0][0], ListenEvent.PAUSE)
        self.assertGreaterEqual(vote.a_listen_data[0][1], start_time)
        self.assertLessEqual(vote.a_listen_data[0][1], end_time)

        vote.pause("b")
        self.assertEqual(len(vote.b_listen_data), 1)
        self.assertEqual(vote.b_listen_data[0][0], ListenEvent.PAUSE)

    def test_sum_listen_time_single_session(self):
        vote = Vote()

        # Simulate a single play/pause session
        base_time = time.time()
        vote.a_listen_data = [
            (ListenEvent.PLAY, base_time),
            (ListenEvent.PAUSE, base_time + 5.0),
        ]

        listen_time = vote.sum_listen_time("a")
        self.assertAlmostEqual(listen_time, 5.0, places=1)

    def test_sum_listen_time_multiple_sessions(self):
        vote = Vote()

        # Simulate multiple play/pause sessions
        base_time = time.time()
        vote.a_listen_data = [
            (ListenEvent.PLAY, base_time),
            (ListenEvent.PAUSE, base_time + 3.0),
            (ListenEvent.PLAY, base_time + 10.0),
            (ListenEvent.PAUSE, base_time + 15.0),
        ]

        listen_time = vote.sum_listen_time("a")
        self.assertAlmostEqual(listen_time, 8.0, places=1)  # 3.0 + 5.0

    def test_sum_listen_time_incomplete_session(self):
        vote = Vote()

        # Simulate incomplete session (play without pause)
        base_time = time.time()
        vote.a_listen_data = [
            (ListenEvent.PLAY, base_time),
            (ListenEvent.PAUSE, base_time + 3.0),
            (ListenEvent.PLAY, base_time + 10.0),  # No corresponding pause
        ]

        listen_time = vote.sum_listen_time("a")
        self.assertAlmostEqual(listen_time, 3.0, places=1)

    def test_sum_listen_time_negative_duration(self):
        vote = Vote()

        # Simulate invalid data with negative duration
        base_time = time.time()
        vote.a_listen_data = [
            (ListenEvent.PLAY, base_time + 5.0),
            (ListenEvent.PAUSE, base_time),  # Pause before play
        ]

        listen_time = vote.sum_listen_time("a")
        self.assertEqual(listen_time, 0.0)

    def test_listen_time_properties(self):
        vote = Vote()

        base_time = time.time()
        vote.a_listen_data = [
            (ListenEvent.PLAY, base_time),
            (ListenEvent.PAUSE, base_time + 3.0),
        ]
        vote.b_listen_data = [
            (ListenEvent.PLAY, base_time),
            (ListenEvent.PAUSE, base_time + 7.0),
        ]

        self.assertAlmostEqual(vote.a_listen_time, 3.0, places=1)
        self.assertAlmostEqual(vote.b_listen_time, 7.0, places=1)

    def test_from_dict(self):
        d = {"preference": Preference.A, "preference_time": 123.456}
        vote = Vote.from_dict(d)
        self.assertEqual(vote.preference, Preference.A)
        self.assertEqual(vote.preference_time, 123.456)

    def test_as_json_dict(self):
        vote = Vote()
        vote.preference = Preference.A
        vote.a_listen_data = [(ListenEvent.PLAY, 123.0), (ListenEvent.PAUSE, 128.0)]
        vote.b_listen_data = [(ListenEvent.PLAY, 130.0)]
        vote.a_feedback = "Great music!"
        vote.b_feedback = "Not my style"

        json_dict = vote.as_json_dict()

        self.assertEqual(json_dict["preference"], "A")
        self.assertEqual(
            json_dict["a_listen_data"], [("PLAY", 123.0), ("PAUSE", 128.0)]
        )
        self.assertEqual(json_dict["b_listen_data"], [("PLAY", 130.0)])
        self.assertEqual(json_dict["a_feedback"], "Great music!")
        self.assertEqual(json_dict["b_feedback"], "Not my style")

    def test_from_json_dict(self):
        d = {
            "preference": "A",
            "preference_time": 123.456,
            "a_listen_data": [("PLAY", 123.0), ("PAUSE", 128.0)],
            "b_listen_data": [("PLAY", 130.0)],
            "a_feedback": "Great music!",
            "b_feedback": "Not my style",
        }
        vote = Vote.from_json_dict(d)

        self.assertEqual(vote.preference, Preference.A)
        self.assertEqual(vote.preference_time, 123.456)
        self.assertEqual(
            vote.a_listen_data, [(ListenEvent.PLAY, 123.0), (ListenEvent.PAUSE, 128.0)]
        )
        self.assertEqual(vote.b_listen_data, [(ListenEvent.PLAY, 130.0)])
        self.assertEqual(vote.a_feedback, "Great music!")
        self.assertEqual(vote.b_feedback, "Not my style")


class TestResponseMetadata(unittest.TestCase):
    def test_from_audio(self):
        # This functionality doesn't exist in the current ResponseMetadata class
        # Just test basic ResponseMetadata creation
        metadata = ResponseMetadata(
            sample_rate=44100,
            num_channels=2,
            duration=1.0,
        )
        self.assertEqual(metadata.sample_rate, 44100)
        self.assertEqual(metadata.num_channels, 2)
        self.assertEqual(metadata.duration, 1.0)

    def test_anonymize(self):
        metadata = ResponseMetadata(
            system_key=SystemKey(system_tag="test-system", variant_tag="test-variant"),
            system_git_hash="test-git-hash",
            generate_start_time=123.0,
            generate_end_time=456.0,
            generate_duration=333.0,
            lyrics="test lyrics",
            sample_rate=44100,
            num_channels=2,
            duration=30.0,
            checksum="test-checksum",
        )

        anon = metadata.anonymize()

        # These should be None after anonymization
        self.assertIsNone(anon.system_key)
        self.assertIsNone(anon.system_git_hash)
        self.assertIsNone(anon.generate_start_time)
        self.assertIsNone(anon.generate_end_time)
        self.assertIsNone(anon.generate_duration)
        self.assertIsNone(anon.sample_rate)
        self.assertIsNone(anon.num_channels)
        self.assertIsNone(anon.duration)

        # These should be preserved
        self.assertEqual(anon.lyrics, "test lyrics")
        self.assertEqual(anon.checksum, "test-checksum")


class TestBattle(unittest.TestCase):
    def test_post_init(self):
        battle = Battle()
        self.assertIsNotNone(battle.uuid)
        battle = Battle(uuid="test-uuid")
        self.assertEqual(battle.uuid, "test-uuid")

    def test_anonymize(self):
        battle = Battle(
            a_metadata=ResponseMetadata(
                system_key=SystemKey(system_tag="a", variant_tag="a-variant")
            ),
            b_metadata=ResponseMetadata(
                system_key=SystemKey(system_tag="b", variant_tag="b-variant")
            ),
        )
        anon = battle.anonymize()
        self.assertIsNone(anon.a_metadata.system_key)
        self.assertIsNone(anon.b_metadata.system_key)
        self.assertIsNotNone(battle.a_metadata.system_key)
        self.assertIsNotNone(battle.b_metadata.system_key)
        self.assertEqual(battle.a_metadata.system_key.system_tag, "a")
        self.assertEqual(battle.a_metadata.system_key.variant_tag, "a-variant")
        self.assertEqual(battle.b_metadata.system_key.system_tag, "b")
        self.assertEqual(battle.b_metadata.system_key.variant_tag, "b-variant")

    def test_from_dict_basic(self):
        d = {
            "prompt": {"prompt": "heavy metal"},
        }
        battle = Battle.from_json_dict(d)
        self.assertEqual(battle.prompt.prompt, "heavy metal")

    def test_from_dict_detailed(self):
        d = {
            "prompt_detailed": {
                "overall_prompt": "heavy metal",
                "instrumental": True,
                "lyrics": None,
            },
        }
        battle = Battle.from_json_dict(d)
        self.assertEqual(battle.prompt_detailed.overall_prompt, "heavy metal")
        self.assertTrue(battle.prompt_detailed.instrumental)

    @patch("music_arena.dataclass.arena.get_secret")
    def test_from_dict_comprehensive(self, mock_get_secret):
        mock_get_secret.return_value = "test-salt"
        d = {
            "uuid": "test-uuid",
            "prompt": {"prompt": "jazz with vocals"},
            "prompt_detailed": {
                "overall_prompt": "jazz with vocals",
                "instrumental": False,
                "lyrics": "test lyrics",
            },
            "prompt_user": {"salted_ip": "test-ip"},
            "prompt_session": {"uuid": "session-uuid", "ack_tos": "test-ack-tos"},
            "a_metadata": {
                "system_key": {"system_tag": "system-a", "variant_tag": "variant-a"},
                "lyrics": "lyrics-a",
            },
            "b_metadata": {
                "system_key": {"system_tag": "system-b", "variant_tag": "variant-b"},
                "lyrics": "lyrics-b",
            },
            "vote": {"preference": "B"},
            "vote_user": {"salted_fingerprint": "test-fingerprint"},
        }
        battle = Battle.from_json_dict(d)  # Use from_json_dict for nested objects

        self.assertEqual(battle.uuid, "test-uuid")
        self.assertEqual(battle.prompt.prompt, "jazz with vocals")
        self.assertEqual(battle.prompt_detailed.overall_prompt, "jazz with vocals")
        self.assertEqual(battle.prompt_user.salted_ip, "test-ip")
        self.assertEqual(battle.prompt_session.uuid, "session-uuid")
        self.assertEqual(battle.prompt_session.ack_tos, "test-ack-tos")
        self.assertEqual(battle.a_metadata.system_key.system_tag, "system-a")
        self.assertEqual(battle.a_metadata.system_key.variant_tag, "variant-a")
        self.assertEqual(battle.a_metadata.lyrics, "lyrics-a")
        self.assertEqual(battle.b_metadata.system_key.system_tag, "system-b")
        self.assertEqual(battle.b_metadata.system_key.variant_tag, "variant-b")
        self.assertEqual(battle.b_metadata.lyrics, "lyrics-b")
        self.assertEqual(battle.vote.preference, Preference.B)
        self.assertEqual(battle.vote_user.salted_fingerprint, "test-fingerprint")

    def test_uuid_uniqueness(self):
        battle1 = Battle()
        battle2 = Battle()
        self.assertNotEqual(battle1.uuid, battle2.uuid)

    def test_anonymize_preserves_other_fields(self):
        original_prompt = SimpleTextToMusicPrompt(prompt="test")
        original_detailed_prompt = DetailedTextToMusicPrompt(
            overall_prompt="test", instrumental=False
        )
        battle = Battle(
            a_metadata=ResponseMetadata(
                system_key=SystemKey(system_tag="a", variant_tag="a-variant"),
                lyrics="lyrics-a",
            ),
            b_metadata=ResponseMetadata(
                system_key=SystemKey(system_tag="b", variant_tag="b-variant"),
                lyrics="lyrics-b",
            ),
            prompt=original_prompt,
            prompt_detailed=original_detailed_prompt,
        )
        anon = battle.anonymize()

        self.assertIsNone(anon.a_metadata.system_key)
        self.assertIsNone(anon.b_metadata.system_key)
        self.assertEqual(anon.prompt, original_prompt)
        self.assertEqual(anon.prompt_detailed, original_detailed_prompt)
        self.assertEqual(anon.a_metadata.lyrics, "lyrics-a")
        self.assertEqual(anon.b_metadata.lyrics, "lyrics-b")
        self.assertIsNotNone(anon.uuid)


if __name__ == "__main__":
    unittest.main()
