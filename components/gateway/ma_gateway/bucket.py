import abc
import pathlib
import shutil
from typing import IO, Optional

from google.cloud import storage


class BucketBase:
    @abc.abstractmethod
    def get(self, key: str, file: Optional[IO[bytes]] = None) -> IO[bytes]: ...

    @abc.abstractmethod
    def put(
        self,
        key: str,
        value: IO[bytes],
        public: bool = False,
        allow_overwrite: bool = False,
    ) -> None: ...

    @abc.abstractmethod
    def get_url(self, key: str) -> str: ...

    @abc.abstractmethod
    def delete(self, key: str) -> None: ...


class LocalBucket(BucketBase):
    def __init__(self, path: pathlib.Path, public_url: Optional[str] = None):
        self.path = path
        self.public_url = public_url

    def get(self, key: str, file: Optional[IO[bytes]] = None) -> IO[bytes]:
        path = self.path / key
        if not path.exists():
            raise FileNotFoundError(f"File {key} not found")
        if file is None:
            return path.open("rb")
        else:
            with path.open("rb") as f:
                shutil.copyfileobj(f, file)
            return file

    def put(
        self,
        key: str,
        value: IO[bytes],
        public: bool = False,
        allow_overwrite: bool = False,
    ) -> None:
        path = self.path / key
        if not allow_overwrite and path.exists():
            raise FileExistsError(f"File {key} already exists")
        with path.open("wb") as f:
            shutil.copyfileobj(value, f)
        if public:
            path.chmod(0o644)
        else:
            path.chmod(0o600)

    def get_url(self, key: str) -> str:
        if self.public_url is None:
            raise ValueError("Public URL is not set")
        return f"{self.public_url}/{key}"

    def delete(self, key: str) -> None:
        (self.path / key).unlink()


class GCPBucket(BucketBase):
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def get(self, key: str, file: Optional[IO[bytes]] = None) -> IO[bytes]:
        blob = self.bucket.blob(key)
        if file is None:
            return blob.download_as_bytes()
        else:
            blob.download_to_file(file)
            return file

    def put(
        self,
        key: str,
        value: IO[bytes],
        public: bool = False,
        allow_overwrite: bool = False,
    ) -> None:
        blob = self.bucket.blob(key)
        if not allow_overwrite and blob.exists():
            raise FileExistsError(f"File {key} already exists")
        blob.upload_from_file(value)
        if public:
            blob.make_public()

    def get_url(self, key: str) -> str:
        blob = self.bucket.blob(key)
        return blob.public_url

    def delete(self, key: str) -> None:
        blob = self.bucket.blob(key)
        blob.delete()
