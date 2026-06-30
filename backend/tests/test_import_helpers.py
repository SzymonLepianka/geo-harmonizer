import zipfile

import pytest

from app.auth import hash_password, verify_password
from app.services.imports import ImportFailure, _safe_extract_zip


def test_password_hash_roundtrip():
    value = hash_password("bardzo-dobre-haslo")
    assert value != "bardzo-dobre-haslo"
    assert verify_password("bardzo-dobre-haslo", value)
    assert not verify_password("inne", value)


def test_zip_path_traversal_is_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../outside.shp", "content")
    with pytest.raises(ImportFailure):
        _safe_extract_zip(archive, tmp_path / "extract")

