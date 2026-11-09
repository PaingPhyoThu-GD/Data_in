"""
Unit tests for FileImportComponent.
"""

from __future__ import annotations
from pathlib import Path
from gemini_ocr.components.file_import import FileImportComponent


def test_file_import_setter_and_getter_single_file(temp_image_dir: Path) -> None:
    component = FileImportComponent()
    sample_img = temp_image_dir / "test_img_1.png"

    component.setter(str(sample_img))
    files = component.getter()

    assert len(files) == 1
    assert files[0] == str(sample_img.resolve())


def test_file_import_setter_directory_expansion(temp_image_dir: Path) -> None:
    component = FileImportComponent()

    # Pass the folder containing 5 PNGs and 1 TXT
    component.setter(str(temp_image_dir))
    files = component.getter()

    # Must find exactly 5 images and exclude the .txt file
    assert len(files) == 5
    for f in files:
        assert f.endswith(".png")


def test_file_import_setter_list_and_deduplication(temp_image_dir: Path) -> None:
    component = FileImportComponent()
    img1 = str(temp_image_dir / "test_img_1.png")
    img2 = str(temp_image_dir / "test_img_2.png")

    # Pass duplicates in list
    component.setter([img1, img2, img1])
    files = component.getter()

    assert len(files) == 2
    assert files == [str(Path(img1).resolve()), str(Path(img2).resolve())]


def test_file_import_ignores_nonexistent_files(tmp_path: Path) -> None:
    component = FileImportComponent()
    nonexistent = str(tmp_path / "does_not_exist.png")

    component.setter(nonexistent)
    files = component.getter()

    assert files == []


def test_file_import_clear(temp_image_dir: Path) -> None:
    component = FileImportComponent()
    component.setter(str(temp_image_dir / "test_img_1.png"))
    assert len(component.getter()) == 1

    component.clear()
    assert component.getter() == []


def test_file_import_supports_jpe_extension(tmp_path: Path) -> None:
    component = FileImportComponent()
    jpe_file = tmp_path / "photo.jpe"
    jpe_file.write_bytes(b"\xff\xd8\xff\xe0dummy_jpe_content")

    component.setter(str(jpe_file))
    files = component.getter()

    assert len(files) == 1
    assert files[0] == str(jpe_file.resolve())


