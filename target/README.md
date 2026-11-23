# auth-service

A deliberately small auth service used to exercise the factory. The Builder works here.

```bash
pytest          # the repo's own suite
python app.py   # run it
```

There is no rate limiting. Adding it is the task; see the spec in `spec/`.

The Builder owns this directory. It cannot see `acceptance/` — that is the Verifier's
independent oracle, deliberately outside this checkout.
