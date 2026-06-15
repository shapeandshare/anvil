"""Factorial computation — recursive and iterative implementations.

Demonstrates:
- Recursive function design with base case and recursive case
- Iterative alternative using a loop
- Type annotations and default parameter values
- Performance comparison between approaches
"""


def factorial_recursive(n: int) -> int:
    """Compute n! recursively.

    Base case: factorial_recursive(0) = 1.
    Recursive case: n * factorial_recursive(n - 1).
    """
    if n < 0:
        raise ValueError(f"Cannot compute factorial of negative number: {n}")
    if n == 0:
        return 1
    return n * factorial_recursive(n - 1)


def factorial_iterative(n: int) -> int:
    """Compute n! iteratively using a loop."""
    if n < 0:
        raise ValueError(f"Cannot compute factorial of negative number: {n}")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def main() -> None:
    """Compare recursive and iterative factorial implementations."""
    test_values = [0, 1, 5, 10]

    for n in test_values:
        rec = factorial_recursive(n)
        itr = factorial_iterative(n)
        status = "OK" if rec == itr else "MISMATCH"
        print(f"n={n:>2}: recursive={rec:>10}, iterative={itr:>10}  [{status}]")


if __name__ == "__main__":
    main()
