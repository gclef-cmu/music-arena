import tempfile
import unittest

import numpy as np

from .audio import Audio, AudioEncoding, dbfs_to_gain, ffprobe_metadata, gain_to_dbfs


class AudioTest(unittest.TestCase):
    def test_basic(self):
        for sr in [8000, 16000, 44100, 48000]:
            for ch in [1, 2]:
                for duration in [0.1, 0.5, 1.0, 2.0]:
                    samples = np.zeros((round(sr * duration), ch), dtype=np.float32)
                    audio = Audio(samples, sr)
                    self.assertEqual(audio.duration, duration)
                    self.assertEqual(audio.sample_rate, sr)
                    self.assertEqual(audio.num_channels, ch)
                    self.assertEqual(audio.num_samples, round(sr * duration))

    def test_set_samples(self):
        # Normal case
        audio = Audio(np.zeros((44100, 2), dtype=np.float32), 44100)
        self.assertEqual(len(audio), 44100)
        self.assertEqual(audio.num_channels, 2)
        self.assertEqual(audio.num_samples, 44100)
        self.assertEqual(audio.duration, 1.0)
        self.assertEqual(audio.sample_rate, 44100)
        self.assertEqual(audio.samples.shape, (44100, 2))
        self.assertEqual(audio.samples.dtype, np.float32)

        # 1D array
        audio.samples = np.zeros(44100, dtype=np.float32)
        self.assertEqual(len(audio), 44100)
        self.assertEqual(audio.num_channels, 1)
        self.assertEqual(audio.num_samples, 44100)
        self.assertEqual(audio.duration, 1.0)

        # 2D array float 64
        audio.samples = np.zeros((44100, 2), dtype=np.float64)
        self.assertEqual(len(audio), 44100)
        self.assertEqual(audio.num_channels, 2)
        self.assertEqual(audio.num_samples, 44100)
        self.assertEqual(audio.duration, 1.0)
        self.assertEqual(audio.samples.shape, (44100, 2))
        self.assertEqual(audio.samples.dtype, np.float32)

        # 3D array
        with self.assertRaises(ValueError):
            audio.samples = np.zeros((44100, 2, 2), dtype=np.float32)

        # int16 array
        with self.assertRaises(TypeError):
            audio.samples = np.zeros((44100, 2), dtype=np.int16)

        # 0 channel array
        with self.assertRaises(ValueError):
            audio.samples = np.zeros((44100, 0), dtype=np.float32)

    def test_resample(self):
        audio = Audio(np.zeros((48000, 2), dtype=np.float32), 48000)
        self.assertEqual(audio.sample_rate, 48000)
        self.assertEqual(audio.num_channels, 2)
        self.assertEqual(audio.num_samples, 48000)
        self.assertEqual(audio.duration, 1.0)
        self.assertEqual(audio.samples.shape, (48000, 2))

        # resample to same sample rate
        audio_re = audio.resample(44100)
        self.assertEqual(audio_re.sample_rate, 44100)
        self.assertEqual(audio_re.num_channels, 2)
        self.assertEqual(audio_re.num_samples, 44100)
        self.assertEqual(audio_re.duration, 1.0)
        self.assertEqual(audio_re.samples.shape, (44100, 2))

    def test_write_and_read(self):
        for sr in [8000, 16000, 44100, 48000]:
            for duration in [0.1, 0.5, 1.0, 2.0]:
                for ch in [1, 2]:
                    samples = np.zeros((round(sr * duration), ch), dtype=np.float32)
                    audio = Audio(samples, sr)
                    self.assertEqual(audio.duration, duration)
                    self.assertEqual(audio.sample_rate, sr)
                    self.assertEqual(audio.num_channels, ch)
                    for encoding in AudioEncoding:
                        with tempfile.NamedTemporaryFile(
                            suffix=f".{encoding.extension}"
                        ) as f:
                            audio.write(f.name, encoding=encoding)
                            metadata = ffprobe_metadata(f.name)
                            audio_rt = Audio.from_file(f.name)
                        self.assertEqual(metadata["sample_rate"], audio.sample_rate)
                        self.assertEqual(metadata["num_channels"], audio.num_channels)
                        self.assertAlmostEqual(
                            metadata["duration"],
                            duration,
                            delta=0.0 if encoding.extension == "wav" else 0.250,
                        )
                        self.assertEqual(audio_rt.sample_rate, audio.sample_rate)
                        self.assertEqual(audio_rt.num_channels, audio.num_channels)
                        self.assertEqual(audio_rt.duration, duration)
                        if encoding.extension == "wav":
                            self.assertTrue(
                                np.allclose(audio.samples, audio_rt.samples)
                            )

    def test_dbfs_gain_conversion(self):
        # Test dbfs_to_gain and gain_to_dbfs conversion functions

        # Test known values
        self.assertAlmostEqual(dbfs_to_gain(0.0), 1.0)
        self.assertAlmostEqual(dbfs_to_gain(-6.0), 0.5, places=1)
        self.assertAlmostEqual(dbfs_to_gain(-20.0), 0.1)
        self.assertAlmostEqual(dbfs_to_gain(-40.0), 0.01)

        # Test gain_to_dbfs
        self.assertAlmostEqual(gain_to_dbfs(1.0), 0.0)
        self.assertAlmostEqual(gain_to_dbfs(0.5), -6.0, places=1)
        self.assertAlmostEqual(gain_to_dbfs(0.1), -20.0)
        self.assertAlmostEqual(gain_to_dbfs(0.01), -40.0)

        # Test round-trip conversion
        test_values = [-60, -40, -20, -12, -6, -3, 0, 3, 6]
        for dbfs_val in test_values:
            gain_val = dbfs_to_gain(dbfs_val)
            dbfs_back = gain_to_dbfs(gain_val)
            self.assertAlmostEqual(dbfs_val, dbfs_back, places=6)

    def test_peak_gain(self):
        # Test peak_gain property

        # Zero audio
        audio = Audio(np.zeros((44100, 2), dtype=np.float32), 44100)
        self.assertEqual(audio.peak_gain, 0.0)

        # Audio with known peak
        samples = np.zeros((44100, 2), dtype=np.float32)
        samples[100, 0] = 0.5
        samples[200, 1] = -0.75
        audio = Audio(samples, 44100)
        self.assertAlmostEqual(audio.peak_gain, 0.75, places=6)

        # Full scale audio
        samples = np.ones((44100, 1), dtype=np.float32)
        audio = Audio(samples, 44100)
        self.assertAlmostEqual(audio.peak_gain, 1.0, places=6)

    def test_crop(self):
        # Test crop method

        # Create test audio with varying samples for verification
        samples = np.arange(44100 * 2, dtype=np.float32).reshape(44100, 2) / 44100.0
        audio = Audio(samples, 44100)

        # Test basic crop
        cropped = audio.crop(duration=0.5)  # crop to 0.5 seconds
        self.assertEqual(cropped.sample_rate, 44100)
        self.assertEqual(cropped.num_channels, 2)
        self.assertEqual(cropped.num_samples, 22050)
        self.assertAlmostEqual(cropped.duration, 0.5, places=6)

        # Test crop with offset
        cropped_offset = audio.crop(duration=0.5, offset=0.25)
        self.assertEqual(cropped_offset.sample_rate, 44100)
        self.assertEqual(cropped_offset.num_channels, 2)
        self.assertEqual(cropped_offset.num_samples, 22050)
        self.assertAlmostEqual(cropped_offset.duration, 0.5, places=6)

        # Verify the offset worked correctly
        expected_start_sample = int(0.25 * 44100)
        np.testing.assert_array_equal(
            cropped_offset.samples,
            audio.samples[expected_start_sample : expected_start_sample + 22050],
        )

        # Test edge cases
        full_crop = audio.crop(duration=1.0)
        self.assertEqual(full_crop.num_samples, audio.num_samples)

        short_crop = audio.crop(duration=0.1)
        self.assertEqual(short_crop.num_samples, 4410)

    def test_peak_normalize(self):
        # Test peak_normalize method

        # Create audio with known peak
        samples = np.zeros((44100, 2), dtype=np.float32)
        samples[100, 0] = 0.5
        samples[200, 1] = -0.25
        audio = Audio(samples.copy(), 44100)

        # Test in-place normalization to 0 dBFS (default)
        original_peak = audio.peak_gain
        normalized = audio.peak_normalize(in_place=True)
        self.assertIs(normalized, audio)  # Should return same object
        self.assertAlmostEqual(audio.peak_gain, 1.0, places=6)

        # Verify scaling was correct
        expected_gain = 1.0 / original_peak
        self.assertAlmostEqual(audio.samples[100, 0], 0.5 * expected_gain, places=6)
        self.assertAlmostEqual(audio.samples[200, 1], -0.25 * expected_gain, places=6)

        # Test not in-place normalization
        samples2 = np.zeros((44100, 2), dtype=np.float32)
        samples2[100, 0] = 0.25
        audio2 = Audio(samples2, 44100)
        original_samples = audio2.samples.copy()

        normalized2 = audio2.peak_normalize(in_place=False)
        self.assertIsNot(normalized2, audio2)  # Should return different object
        np.testing.assert_array_equal(
            audio2.samples, original_samples
        )  # Original unchanged
        self.assertAlmostEqual(normalized2.peak_gain, 1.0, places=6)

        # Test custom peak dBFS
        samples3 = np.zeros((44100, 1), dtype=np.float32)
        samples3[100, 0] = 0.5
        audio3 = Audio(samples3, 44100)

        normalized3 = audio3.peak_normalize(in_place=True, peak_dbfs=-6.0)
        expected_peak = dbfs_to_gain(-6.0)
        self.assertAlmostEqual(audio3.peak_gain, expected_peak, places=6)

        # Test zero audio (should not change)
        zero_audio = Audio(np.zeros((44100, 1), dtype=np.float32), 44100)
        original_zero_samples = zero_audio.samples.copy()
        zero_audio.peak_normalize(in_place=True)
        np.testing.assert_array_equal(zero_audio.samples, original_zero_samples)


if __name__ == "__main__":
    unittest.main()
