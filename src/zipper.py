"""
Create ZIP files from extracted file data.
"""

import zipfile
import io
import os
from pathlib import Path
from .parser import ExtractedFile


def create_zip_bytes(files: list[ExtractedFile], root_folder: str = '') -> bytes:
    """Create a ZIP archive in memory and return as bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            path = f.path
            if root_folder:
                path = f'{root_folder}/{path}'
            zf.writestr(path, f.content)
    return buf.getvalue()


def create_zip_file(files: list[ExtractedFile], output_path: str, root_folder: str = ''):
    """Create a ZIP archive on disk."""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            path = f.path
            if root_folder:
                path = f'{root_folder}/{path}'
            zf.writestr(path, f.content)


def extract_to_folder(files: list[ExtractedFile], output_dir: str, root_folder: str = ''):
    """Extract files to a folder on disk."""
    base = Path(output_dir)
    if root_folder:
        base = base / root_folder

    for f in files:
        file_path = base / f.path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f.content, encoding='utf-8')
