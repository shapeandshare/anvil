"""A friendly hello world program with user input/output.

Demonstrates:
- Function definition and docstrings
- User input via input()
- String formatting with f-strings
- The __name__ == '__main__' idiom
"""


def greet(name: str) -> str:
    """Return a personalized greeting for the given name."""
    return f"Hello, {name}! Welcome to Python programming."


def main() -> None:
    """Run the interactive greeting program."""
    print("=== Greeting Program ===")
    user_name = input("What is your name? ")
    message = greet(user_name)
    print(message)
    print(f"Your name has {len(user_name)} characters.")


if __name__ == "__main__":
    main()
