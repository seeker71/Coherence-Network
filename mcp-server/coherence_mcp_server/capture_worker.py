"""Retired detached transcript worker, retained for already queued invocations.

No argument is opened or processed. A background invocation cannot establish
consent for a selected learning excerpt, and failures never fall back to raw
transcript capture. The explicit ``coherence_capture`` tool owns local writes.
"""


def main() -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
