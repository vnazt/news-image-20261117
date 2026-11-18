#!/usr/bin/env python3
"""Entry program for the make.fun bounty news-image-20261117 (v2).

The v2 front page: "34 stories, 5 continents — one front page summing up
Tuesday 17 November 2026". The deliverable is a single PNG, entry.png,
kept beside this file. The program validates the image against the bounty
limits and copies it, byte for byte, into the output directory
(MAKEFUN_OUTPUT_DIR, or /output when that is not set).

Validation covers the PNG signature, the IHDR dimensions (within the
1024x1024 bounty limit and, for this front page, exactly 1024x1024), and
the file size (at most 1 MiB). On success the program prints a one-line
summary of everything it verified.

Python 3.13, standard library only, no network access.
"""

import os
import struct
import sys

MAX_DIMENSION = 1024          # bounty limit: width and height each <= 1024 px
EXPECTED_DIMENSION = 1024     # this front page is exactly 1024x1024
MAX_SIZE_BYTES = 1_048_576    # the image file must be <= 1 MiB
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class CheckFailure(ValueError):
    """A named validation check failed; the message names the check."""


def _fail(check, detail):
    raise CheckFailure(f"check '{check}' failed: {detail}")


def run_checks(path):
    """Validate the bundled front page, check by check.

    Returns (passed, size), where passed is the list of check descriptions
    that succeeded, in the order they ran. Raises CheckFailure naming the
    first failed check when the image is missing, is not a PNG, is not
    exactly 1024x1024, or breaks a bounty limit.
    """
    passed = []

    if not os.path.isfile(path):
        _fail("file-present", f"entry image not found: {path}")
    passed.append("file present")

    size = os.path.getsize(path)
    if size > MAX_SIZE_BYTES:
        _fail(
            "file-size",
            f"entry image is {size} bytes, over the "
            f"{MAX_SIZE_BYTES}-byte limit",
        )
    if size < 24:
        _fail("file-size", "entry image is too small to be a valid PNG")
    passed.append(f"file size {size} bytes <= {MAX_SIZE_BYTES}")

    with open(path, "rb") as handle:
        header = handle.read(24)

    if header[:8] != PNG_SIGNATURE:
        _fail(
            "png-signature",
            "entry image does not start with the PNG signature",
        )
    passed.append("PNG signature")

    # The first chunk of a PNG is IHDR; its data starts with width, height.
    if header[12:16] != b"IHDR":
        _fail("ihdr-chunk", "entry image has no IHDR chunk after the signature")
    width, height = struct.unpack(">II", header[16:24])
    passed.append(f"IHDR dimensions {width}x{height}")

    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        _fail(
            "dimension-limit",
            f"entry image is {width}x{height}, over the "
            f"{MAX_DIMENSION}x{MAX_DIMENSION} limit",
        )
    passed.append(f"within the {MAX_DIMENSION}x{MAX_DIMENSION} limit")

    if width != EXPECTED_DIMENSION or height != EXPECTED_DIMENSION:
        _fail(
            "dimension-exact",
            f"entry image is {width}x{height}, but the v2 front page "
            f"must be exactly {EXPECTED_DIMENSION}x{EXPECTED_DIMENSION}",
        )
    passed.append(f"exactly {EXPECTED_DIMENSION}x{EXPECTED_DIMENSION}")

    return passed, size


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
    passed, expected_size = run_checks(source)

    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(output_dir, exist_ok=True)
    destination = os.path.join(output_dir, "entry.png")

    written = copy_image(source, destination)
    if written != expected_size:
        _fail(
            "copy-size",
            f"wrote {written} bytes, expected {expected_size}",
        )

    print(
        "verified entry.png: "
        + "; ".join(passed)
        + f"; copied byte-for-byte to {destination} ({written} bytes)"
    )


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
