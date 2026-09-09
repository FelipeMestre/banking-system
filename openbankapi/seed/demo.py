"""Alias so `python -m openbankapi.seed.demo` works as well as `.run`."""
from openbankapi.seed.run import main

if __name__ == "__main__":
    raise SystemExit(main())
