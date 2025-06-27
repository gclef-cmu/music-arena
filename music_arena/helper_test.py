import unittest

from music_arena.helper import checksum, create_uuid, salted_checksum


class HelperTest(unittest.TestCase):
    def test_create_uuid(self):
        uuid1 = create_uuid()
        uuid2 = create_uuid()
        self.assertEqual(len(uuid1), 36)
        self.assertEqual(len(uuid2), 36)
        self.assertNotEqual(uuid1, uuid2)

    def test_checksum(self):
        self.assertEqual(checksum("foo"), "acbd18db4cc2f85cedef654fccc4a4d8")
        self.assertEqual(checksum("bar"), "37b51d194a7513e45b56f6524f2d51f2")
        with self.assertRaises(ValueError):
            checksum(b"test", strategy="sha256")

    def test_salted_checksum(self):
        self.assertEqual(
            salted_checksum("foo", salt="salt1"), "90d11c5a73186f46fea58427d66acc5c"
        )
        self.assertNotEqual(salted_checksum("foo", salt="salt1"), checksum("foo"))
        self.assertEqual(
            salted_checksum("bar", salt="salt1"), "4d4f820833956f6cac463d7dc2f7f36e"
        )
        self.assertNotEqual(salted_checksum("bar", salt="salt1"), checksum("bar"))
        self.assertEqual(
            salted_checksum("foo", salt="salt2"), "7e36ec146fdbd0874829eebd0e7af31a"
        )
        self.assertNotEqual(
            salted_checksum("foo", salt="salt2"), salted_checksum("foo", salt="salt1")
        )
        self.assertEqual(
            salted_checksum("foo", salt=""), "acbd18db4cc2f85cedef654fccc4a4d8"
        )
        self.assertEqual(salted_checksum("foo", salt=""), checksum("foo"))


if __name__ == "__main__":
    unittest.main()
