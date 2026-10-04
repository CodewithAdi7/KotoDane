"""Run OCR against a local sample image and optionally check its expected text."""

from __future__ import annotations

import argparse
from pathlib import Path

from ocr import recognize


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Path to your cropped manga image")
    parser.add_argument(
        "--expected",
        help="Expected Japanese text; when provided, compare it to the OCR result",
    )
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Image file does not exist: {args.image}")

    recognized_text = recognize(args.image.read_bytes())
    print(f"OCR result: {recognized_text}")

    if args.expected is not None:
        normalize = lambda value: "".join(value.split())
        if normalize(recognized_text) != normalize(args.expected):
            print(f"Expected:   {args.expected}")
            return 1
        print("OCR text matches the expected text.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
