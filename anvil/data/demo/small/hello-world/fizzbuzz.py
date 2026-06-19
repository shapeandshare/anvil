"""Classic FizzBuzz — the quintessential programming interview problem.

Demonstrates:
- Modulo arithmetic and conditional logic
- Clean branching with elif
- Loop control with range()
- Separating output logic from business logic
"""


def fizzbuzz(n: int) -> str:
    """Return the FizzBuzz value for a single integer.

    Rules:
    - Divisible by 3 and 5 → "FizzBuzz"
    - Divisible by 3 only  → "Fizz"
    - Divisible by 5 only  → "Buzz"
    - Otherwise           → the number as a string
    """
    if n % 3 == 0 and n % 5 == 0:
        return "FizzBuzz"
    if n % 3 == 0:
        return "Fizz"
    if n % 5 == 0:
        return "Buzz"
    return str(n)


def main() -> None:
    """Print FizzBuzz for numbers 1 through 100."""
    print("=== FizzBuzz (1-100) ===")
    for i in range(1, 101):
        print(fizzbuzz(i))


if __name__ == "__main__":
    main()
