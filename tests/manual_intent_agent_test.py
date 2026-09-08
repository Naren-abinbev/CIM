from __future__ import annotations

import json

from backend.ai.agents.intent_agent import analyze_intent


def display_result(result: dict) -> None:
    """Display the complete agent result."""

    print("\nAgent result:")
    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


def main() -> None:
    """Run the agent interactively."""

    print("=" * 65)
    print("CIM Gemini Intent Agent")
    print("=" * 65)
    print("Enter an IT incident description.")
    print("Type exit, quit, or q to stop.")

    while True:
        try:
            description = input(
                "\nDescription: "
            ).strip()

            if description.lower() in {
                "exit",
                "quit",
                "q",
            }:
                print("Manual testing stopped.")
                break

            result = analyze_intent(description)
            display_result(result)

        except KeyboardInterrupt:
            print("\nManual testing stopped.")
            break

        except EOFError:
            print("\nManual testing stopped.")
            break

        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "message": (
                            "Unexpected manual test failure."
                        ),
                        "error": (
                            f"{type(exc).__name__}: {exc}"
                        ),
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    main()