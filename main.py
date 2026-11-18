"""Entry program for the make.fun bounty "news-image-20261117".

The entry itself is ``entry.png``: a dense broadsheet front page,
"34 stories, 5 continents", summing up the world news of
Tuesday 17 November 2026 in one 1024x1024 image.

This script is the delivery mechanism.  It verifies that the bundled
image satisfies every rule of the competition (present, within the
size cap, a genuine PNG, and exactly 1024x1024) and then copies it,
byte for byte, into the output directory chosen by the runner:
``$MAKEFUN_OUTPUT_DIR`` when that variable is set, ``/output``
otherwise.  Any failed check aborts with a non-zero exit status and
an error message that names the check that failed.
"""

import os
import shutil
import struct
import sys

# Competition limits.
MAX_BYTES = 1_048_576          # 1 MiB hard cap on the image file.
MAX_SIDE = 1024                # neither dimension may exceed this.
WANT_WIDTH = 1024              # the entry is exactly this wide ...
WANT_HEIGHT = 1024             # ... and exactly this tall.

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
IMAGE_NAME = "entry.png"


class CheckFailed(Exception):
    """Raised when one named validation check does not pass."""


def image_path() -> str:
    """Absolute path of the image bundled next to this script."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, IMAGE_NAME)


def check_exists(path: str) -> None:
    if not os.path.isfile(path):
        raise CheckFailed(f"exists: {IMAGE_NAME} not found beside the script")


def check_size(path: str) -> int:
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        raise CheckFailed(
            f"size: {IMAGE_NAME} is {size} bytes, over the {MAX_BYTES}-byte cap"
        )
    return size


def read_header(path: str) -> bytes:
    """Return the first 24 bytes: signature plus the IHDR dimensions."""
    with open(path, "rb") as fh:
        return fh.read(24)


def check_signature(header: bytes) -> None:
    if len(header) < len(PNG_MAGIC) or not header.startswith(PNG_MAGIC):
        raise CheckFailed("signature: file does not start with the PNG signature")


def png_dimensions(header: bytes) -> tuple[int, int]:
    """Width and height stored in the IHDR chunk (bytes 16..24)."""
    if len(header) < 24:
        raise CheckFailed("ihdr: file too short to contain an IHDR header")
    if header[12:16] != b"IHDR":
        raise CheckFailed("ihdr: first chunk is not the IHDR chunk")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def check_dimensions(width: int, height: int) -> None:
    if width > MAX_SIDE or height > MAX_SIDE:
        raise CheckFailed(
            f"bounds: image is {width}x{height}, a side exceeds {MAX_SIDE}"
        )
    if (width, height) != (WANT_WIDTH, WANT_HEIGHT):
        raise CheckFailed(
            f"dimensions: image is {width}x{height}, "
            f"expected exactly {WANT_WIDTH}x{WANT_HEIGHT}"
        )


def output_dir() -> str:
    return os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"


def main() -> int:
    src = image_path()
    try:
        check_exists(src)
        size = check_size(src)
        header = read_header(src)
        check_signature(header)
        width, height = png_dimensions(header)
        check_dimensions(width, height)
    except CheckFailed as exc:
        print(f"error: check failed [{exc}]", file=sys.stderr)
        return 1

    dest_dir = output_dir()
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, IMAGE_NAME)
    shutil.copyfile(src, dest)

    # A short or corrupted copy must never pass as a successful run:
    # confirm the destination landed with exactly the source's bytes.
    if os.path.getsize(dest) != size:
        print(
            f"error: check failed [copy: {dest} does not match the "
            f"source size of {size} bytes]",
            file=sys.stderr,
        )
        return 1

    print(
        "ok: checks passed (exists, size<={} bytes [{}], png-signature, "
        "ihdr {}x{} within {}, exact {}x{}) -> {}".format(
            MAX_BYTES, size, width, height, MAX_SIDE,
            WANT_WIDTH, WANT_HEIGHT, dest,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
