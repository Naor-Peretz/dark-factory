"""The factory's cross-cycle memory. Agents call this; they do not import cognee.

    python scripts/memory.py remember --spec auth-rate-limit --role gatekeeper \
        --text "Blocked because criterion 6 said 'clean checkout' but the workspace
                had no git history, so it could not be demonstrated."

    python scripts/memory.py recall --spec auth-rate-limit "what blocked previous cycles?"
    python scripts/memory.py recall "retry-after"          # across all specs
    python scripts/memory.py status                        # is anything stored?

Writes are serialized by a file lock, because cognee's embedded graph is documented as
unsafe for concurrent use from separate processes -- and the crew is four processes.

Exit codes: 0 fine, 1 nothing found (recall), 2 usage/config problem, 3 backend failure.
A backend failure is deliberately NOT fatal to the caller's cycle: a factory that cannot
remember should still be able to build. The agent prompts say to carry on and note it.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory.memory import (  # noqa: E402
    DATASET,
    Lesson,
    configure_env,
    quiet_logging,
    writer_lock,
)


def _search_type(name: str = "CHUNKS"):
    """Find SearchType without betting on one import path across versions.

    Without an explicit query_type and with no LLM key, recall defaults to a completion
    mode and returns an assembled prompt rather than passages. We want the passages.
    """
    for mod in ("cognee", "cognee.modules.search.types", "cognee.api.v1.search"):
        try:
            m = __import__(mod, fromlist=["SearchType"])
            st = getattr(m, "SearchType", None)
            if st is not None and hasattr(st, name):
                return getattr(st, name)
        except Exception:
            continue
    return None


async def do_remember(spec: str, role: str, text: str) -> int:
    configure_env()
    import cognee

    quiet_logging()

    lesson = Lesson(spec_id=spec, role=role, text=text)
    with writer_lock():
        try:
            await cognee.remember(lesson.render(), dataset_name=DATASET)
        except Exception as e:  # noqa: BLE001 - a memory failure must not kill a cycle
            print(f"memory unavailable: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
            return 3
    print(f"remembered [{spec}/{role}] {text[:70]}{'...' if len(text) > 70 else ''}")
    return 0


async def do_recall(query: str, spec: str | None, top_k: int) -> int:
    configure_env()
    import cognee

    quiet_logging()

    scoped = f"[spec:{spec}] {query}" if spec else query
    st = _search_type("CHUNKS")
    kwargs = {"datasets": [DATASET], "top_k": top_k}
    if st is not None:
        kwargs["query_type"] = st

    with writer_lock():
        try:
            results = await cognee.recall(scoped, **kwargs)
        except Exception as e:  # noqa: BLE001
            print(f"memory unavailable: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
            return 3

    rows = []
    for r in results or []:
        # Local mode returns Pydantic objects; remote mode returns plain dicts.
        text = getattr(r, "text", None) or (r.get("text") if isinstance(r, dict) else None)
        if not text:
            text = str(r)
        if spec and f"[spec:{spec}]" not in text:
            continue  # the query is a hint, not a filter -- enforce the scope ourselves
        rows.append(text.strip())

    if not rows:
        print("no prior lessons found" + (f" for spec {spec}" if spec else ""))
        return 1

    print(f"{len(rows)} prior lesson(s):")
    for t in rows:
        print(f"  - {t}")
    return 0


async def do_status() -> int:
    configure_env()
    from factory.memory import DATA_DIR, SYSTEM_DIR

    print(f"system dir: {SYSTEM_DIR}  (exists: {SYSTEM_DIR.exists()})")
    print(f"data dir:   {DATA_DIR}  (exists: {DATA_DIR.exists()})")
    try:
        import cognee  # noqa: F401
    except ImportError:
        print("cognee is NOT installed", file=sys.stderr)
        return 2
    return await do_recall("lesson", None, 50)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("remember", help="store a lesson from this cycle")
    r.add_argument("--spec", required=True)
    r.add_argument("--role", required=True,
                   choices=["architect", "builder", "verifier", "gatekeeper", "human"])
    r.add_argument("--text", required=True)

    c = sub.add_parser("recall", help="what did earlier cycles learn?")
    c.add_argument("query")
    c.add_argument("--spec", default=None)
    c.add_argument("--top-k", type=int, default=10)

    sub.add_parser("status", help="show where memory lives and what is in it")

    args = ap.parse_args()
    if args.cmd == "remember":
        return asyncio.run(do_remember(args.spec, args.role, args.text))
    if args.cmd == "recall":
        return asyncio.run(do_recall(args.query, args.spec, args.top_k))
    return asyncio.run(do_status())


if __name__ == "__main__":
    raise SystemExit(main())
