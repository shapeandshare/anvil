# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Display diff between progressive training stages."""
import sys
from pathlib import Path


def show_diff(file_a: str, file_b: str) -> None:
    """Print a line-by-line diff of two files.

    Parameters
    ----------
    file_a : str
        Path to the first (older) file.
    file_b : str
        Path to the second (newer) file.
    """
    a_path = Path(file_a).resolve(strict=True)
    b_path = Path(file_b).resolve(strict=True)
    if not a_path.is_file():
        print(f"Error: not a file: {a_path}")
        return
    if not b_path.is_file():
        print(f"Error: not a file: {b_path}")
        return
    a_lines = a_path.read_text().splitlines(keepends=True)
    b_lines = b_path.read_text().splitlines(keepends=True)
    for i, (la, lb) in enumerate(zip(a_lines, b_lines)):
        if la != lb:
            print(f"Line {i + 1}:")
            print(f"  - {la.rstrip()}")
            print(f"  + {lb.rstrip()}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Usage: python examples/diff_stages.py examples/train0.py examples/train1.py"
        )
    else:
        show_diff(sys.argv[1], sys.argv[2])
