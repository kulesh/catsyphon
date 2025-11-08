"""Custom exceptions for CatSyphon."""


class DuplicateFileError(Exception):
    """Raised when attempting to ingest a file that has already been processed."""

    def __init__(self, file_hash: str, file_path: str | None = None):
        self.file_hash = file_hash
        self.file_path = file_path
        message = f"File with hash {file_hash} has already been processed"
        if file_path:
            message += f": {file_path}"
        super().__init__(message)
