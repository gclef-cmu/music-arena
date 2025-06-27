import enum
import pathlib
import subprocess
from typing import IO, Any

import numpy as np
import resampy
import soundfile as sf


class AudioEncoding(enum.Enum):
    WAV_S16 = "WAV_S16"
    WAV_F32 = "WAV_F32"
    MP3_V0 = "MP3_V0"

    @property
    def extension(self) -> str:
        if self == AudioEncoding.WAV_S16:
            return "wav"
        elif self == AudioEncoding.WAV_F32:
            return "wav"
        elif self == AudioEncoding.MP3_V0:
            return "mp3"


class Audio:
    def __init__(self, samples: np.ndarray, sample_rate: int):
        self.samples = samples
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive")
        self._sample_rate = sample_rate

    def __len__(self) -> int:
        return self.num_samples

    @property
    def sample_rate(self):
        return self._sample_rate

    @sample_rate.setter
    def sample_rate(self, value: int):
        del value
        raise AssertionError("Sample rate should not be changed")

    @property
    def samples(self):
        return self._samples

    @samples.setter
    def samples(self, value: np.ndarray):
        if value.ndim == 1:
            value = value[:, np.newaxis]
        if value.ndim != 2:
            raise ValueError("Audio samples must be 2D")
        if value.dtype == np.float64:
            value = value.astype(np.float32)
        if value.dtype != np.float32:
            raise TypeError("Audio samples must be float32")
        if value.shape[1] < 1:
            raise ValueError("Audio samples must have at least one channel")
        self._samples = value

    @property
    def num_samples(self) -> int:
        return self.samples.shape[0]

    @property
    def num_channels(self) -> int:
        return self.samples.shape[1]

    @property
    def duration(self) -> float:
        return len(self) / self.sample_rate

    @property
    def peak_gain(self) -> float:
        return float(np.max(np.abs(self.samples)))

    def crop(self, duration: float, offset: float = 0.0) -> "Audio":
        start_sample = int(offset * self.sample_rate)
        end_sample = start_sample + int(duration * self.sample_rate)
        return Audio(
            samples=self.samples[start_sample:end_sample],
            sample_rate=self.sample_rate,
        )

    def peak_normalize(self, in_place: bool = True, peak_dbfs: float = 0.0) -> "Audio":
        if in_place:
            if self.peak_gain > 0.0:
                self.samples *= dbfs_to_gain(peak_dbfs) / self.peak_gain
            return self
        else:
            result = Audio(samples=self.samples.copy(), sample_rate=self.sample_rate)
            return result.peak_normalize(in_place=True)

    def resample(self, new_sample_rate: int, **kwargs) -> "Audio":
        if new_sample_rate == self.sample_rate:
            return self
        new_samples = resampy.resample(
            self.samples.swapaxes(0, 1), self.sample_rate, new_sample_rate, **kwargs
        )
        return Audio(samples=new_samples.swapaxes(0, 1), sample_rate=new_sample_rate)

    @classmethod
    def from_file(cls, file: str | pathlib.Path | IO) -> "Audio":
        samples, sample_rate = sf.read(file, dtype="float32")
        return cls(samples=samples, sample_rate=sample_rate)

    def write(
        self,
        file: str | pathlib.Path | IO,
        encoding: AudioEncoding = AudioEncoding.WAV_S16,
    ):
        sf_write_kwargs: dict[str, Any] = {}
        if encoding == AudioEncoding.WAV_S16:
            sf_write_kwargs["format"] = "WAV"
            sf_write_kwargs["subtype"] = "PCM_16"
        elif encoding == AudioEncoding.WAV_F32:
            sf_write_kwargs["format"] = "WAV"
            sf_write_kwargs["subtype"] = "FLOAT"
        elif encoding == AudioEncoding.MP3_V0:
            sf_write_kwargs["format"] = "MP3"
            sf_write_kwargs["bitrate_mode"] = "VARIABLE"
            sf_write_kwargs["compression_level"] = 0
        else:
            raise ValueError(f"Unsupported encoding: {encoding}")
        sf.write(file, self.samples, self.sample_rate, **sf_write_kwargs)


def dbfs_to_gain(dbfs: float) -> float:
    return 10.0 ** (dbfs / 20.0)


def gain_to_dbfs(gain: float) -> float:
    return 20.0 * np.log10(gain)


def ffprobe_metadata(file: str | pathlib.Path) -> dict[str, float | int]:
    if not pathlib.Path(file).exists():
        raise FileNotFoundError(f"File not found: {file}")
    output = (
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=sample_rate,channels",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(file),
            ]
        )
        .decode("utf-8")
        .strip()
        .splitlines()
    )

    return {
        "sample_rate": round(float(output[0])),
        "num_channels": int(output[1]),
        "duration": float(output[2]),
    }
