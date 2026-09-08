from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


class ReportStorageError(RuntimeError):
    pass


class ReportFileTooLargeError(ReportStorageError):
    pass


@dataclass(frozen=True)
class StoredReportFile:
    storage_key: str
    path: Path
    file_size_bytes: int
    sha256: str
    header: bytes


class LocalReportStorage:
    _STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.pdf$")
    _MAX_STORAGE_KEY_ATTEMPTS = 3
    _MAX_CLEANUP_ATTEMPTS = 3

    def __init__(
        self,
        *,
        root: Path,
        max_file_size_bytes: int,
        chunk_size_bytes: int = 64 * 1024,
    ) -> None:
        if max_file_size_bytes <= 0:
            raise ValueError("max_file_size_bytes must be positive.")
        if chunk_size_bytes <= 0:
            raise ValueError("chunk_size_bytes must be positive.")

        self.root = Path(root).resolve()
        self.max_file_size_bytes = max_file_size_bytes
        self.chunk_size_bytes = chunk_size_bytes

    def save(self, source: BinaryIO) -> StoredReportFile:
        self.root.mkdir(parents=True, exist_ok=True)

        for _ in range(self._MAX_STORAGE_KEY_ATTEMPTS):
            storage_key = f"{uuid.uuid4().hex}.pdf"
            path = self._path_for_key(storage_key)
            created_by_this_save = False
            digest = hashlib.sha256()
            file_size_bytes = 0
            header = b""

            try:
                with path.open("xb") as destination:
                    created_by_this_save = True
                    while True:
                        chunk = source.read(self.chunk_size_bytes)
                        if not chunk:
                            break
                        if not isinstance(chunk, bytes):
                            raise ReportStorageError("Report upload stream is invalid.")

                        file_size_bytes += len(chunk)
                        if file_size_bytes > self.max_file_size_bytes:
                            raise ReportFileTooLargeError(
                                "Report file exceeds the maximum allowed size."
                            )

                        if len(header) < 5:
                            header += chunk[: 5 - len(header)]
                        digest.update(chunk)
                        destination.write(chunk)
            except FileExistsError:
                continue
            except Exception:
                if created_by_this_save:
                    self._cleanup_failed_save(storage_key)
                raise

            return StoredReportFile(
                storage_key=storage_key,
                path=path,
                file_size_bytes=file_size_bytes,
                sha256=digest.hexdigest(),
                header=header,
            )

        raise ReportStorageError("Unable to allocate report storage.")

    def cleanup(self, storage_key: str) -> None:
        path = self._path_for_key(storage_key)
        last_error: OSError | None = None

        for _ in range(self._MAX_CLEANUP_ATTEMPTS):
            try:
                path.unlink()
                return
            except FileNotFoundError:
                return
            except OSError as exc:
                last_error = exc

        raise ReportStorageError("Stored report file could not be removed.") from last_error

    def _cleanup_failed_save(self, storage_key: str) -> None:
        try:
            self.cleanup(storage_key)
        except ReportStorageError as exc:
            raise ReportStorageError("Report storage cleanup failed.") from exc

    def _path_for_key(self, storage_key: str) -> Path:
        if not self._STORAGE_KEY_PATTERN.fullmatch(storage_key):
            raise ReportStorageError("Invalid report storage key.")

        path = (self.root / storage_key).resolve()
        if path.parent != self.root:
            raise ReportStorageError("Invalid report storage key.")
        return path
