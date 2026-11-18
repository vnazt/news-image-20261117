#!/usr/bin/env python3
"""Entry program for the make.fun bounty news-image-20261117.

"Sum up 17 November's world news in one image": the deliverable is a single
PNG, entry.png, kept beside this file. The program validates the image
against the bounty limits and copies it, byte for byte, into the output
directory (MAKEFUN_OUTPUT_DIR, or /output when that is not set).

Python 3.13, standard library only, no network access.
"""

import os
import struct
import sys

MAX_DIMENSION = 1024          # width and height must each be <= 1024 px
MAX_SIZE_BYTES = 1_048_576    # the image file must be <= 1 MiB
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def validate_image(path):
    """Check that path holds a PNG within the bounty limits.

    Returns the file size in bytes. Raises ValueError with a clear message
    when the image is missing, is not a PNG, or breaks a limit.
    """
    if not os.path.isfile(path):
        raise ValueError(f"entry image not found: {path}")

    size = os.path.getsize(path)
    if size > MAX_SIZE_BYTES:
        raise ValueError(
            f"entry image is {size} bytes, over the {MAX_SIZE_BYTES}-byte limit"
        )
    if size < 24:
        raise ValueError("entry image is too small to be a valid PNG")

    with open(path, "rb") as handle:
        header = handle.read(24)

    if header[:8] != PNG_SIGNATURE:
        raise ValueError("entry image does not start with the PNG signature")

    # The first chunk of a PNG is IHDR; its data starts with width, height.
    if header[12:16] != b"IHDR":
        raise ValueError("entry image has no IHDR chunk after the signature")
    width, height = struct.unpack(">II", header[16:24])
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise ValueError(
            f"entry image is {width}x{height}, over the "
            f"{MAX_DIMENSION}x{MAX_DIMENSION} limit"
        )
    return size


COPY_CHUNK_BYTES = 64 * 1024  # copy in 64 KiB chunks, never whole-file


def copy_image(source, destination):
    """Copy source to destination in chunks; return the byte count written."""
    written = 0
    with open(source, "rb") as src, open(destination, "wb") as dst:
        while True:
            chunk = src.read(COPY_CHUNK_BYTES)
            if not chunk:
                break
            dst.write(chunk)
            written += len(chunk)
    return written


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, "entry.png")
    expected_size = validate_image(source)

    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(output_dir, exist_ok=True)
    destination = os.path.join(output_dir, "entry.png")

    written = copy_image(source, destination)
    if written != expected_size:
        raise ValueError(
            f"copy check failed: wrote {written} bytes, "
            f"expected {expected_size}"
        )

    print(f"entry.png copied to {destination} ({written} bytes, verified)")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)