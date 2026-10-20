"""Retired automatic transcript capture entrypoint.

Older installations may still invoke this hook. It deliberately reads no input,
opens no transcript, and starts no worker. Learning uses the explicit
``coherence_capture`` tool with a user-selected excerpt and its consent receipt.
"""


def main() -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
