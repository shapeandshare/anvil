"""Display diff between progressive training stages."""
import sys


def show_diff(file_a, file_b):
    with open(file_a) as f:
        a_lines = f.readlines()
    with open(file_b) as f:
        b_lines = f.readlines()
    for i, (la, lb) in enumerate(zip(a_lines, b_lines)):
        if la != lb:
            print(f"Line {i+1}:")
            print(f"  - {la.rstrip()}")
            print(f"  + {lb.rstrip()}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python examples/diff_stages.py examples/train0.py examples/train1.py")
    else:
        show_diff(sys.argv[1], sys.argv[2])