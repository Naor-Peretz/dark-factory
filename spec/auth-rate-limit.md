rev: 1

# PLACEHOLDER SPEC — stand-in until the real challenge is loaded

> This is **not** the buildathon challenge. It is a deliberately small target with sharp
> test signal, used to exercise the factory end to end before the real spec arrives.
> Drop the real challenge into `spec/` as a `.md` file with an
> `## Acceptance criteria` section and delete this file.
>
> Chosen because every criterion below fails loudly and specifically when unmet, which
> gives the Verifier real teeth. A target with vague criteria makes the whole factory
> look like agents agreeing with each other.

## Goal

Add request rate limiting to the authentication endpoint so that credential-stuffing
attempts are throttled without affecting legitimate traffic.

## Constraints

- The limiter lives in middleware. Do not modify the auth handler itself.
- Per-IP limiting. No shared global bucket.
- In-memory is acceptable; no new infrastructure dependency.
- The window length and request budget must stay constructor parameters of
  `create_app(window_seconds=60, max_requests=10)`, so the behavior is testable without
  waiting a real minute. Do not hard-code 60.

## Acceptance criteria

- the 11th request from one IP within 60s returns HTTP 429
- the 10th request from one IP within 60s still returns its normal status
- the limiter resets after the 60s window elapses, and the next request succeeds
- a 429 response carries a Retry-After header with the remaining seconds
- two different IPs have independent budgets
- the existing suite in `tests/` still passes from a clean checkout
- valid credentials still succeed while within budget

## Out of scope

Distributed rate limiting, per-user (as opposed to per-IP) budgets, and admin bypass.
