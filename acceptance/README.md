# Acceptance oracle

The Verifier's independent check. **The Builder cannot see this directory.**

`factory/build.py` gives the Builder `cwd=workspace/repo` and nothing else. The Verifier
gets the same `cwd` plus this directory through the adapter's `add_dirs`, so it can run
these tests while the Builder can neither read nor edit them.

That asymmetry is the point. A critic that can read the author's own tests is not an
independent check, and one that can edit them is no check at all. These tests also probe
things a Builder writing its own tests would plausibly miss — a shared global bucket that
satisfies "the 11th request is throttled" while violating the per-IP constraint, and a
`Retry-After` that is present but not a plausible number.

```bash
# from workspace/repo, as the Verifier runs it
pytest /home/naor/Dark_Factory/acceptance -v
```
