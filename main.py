"""Primary domain CLI. Historical helpers remain available through lazy compatibility."""
from opinion_gateway.cli import main

def __getattr__(name):
    from legacy import main as previous
    return getattr(previous,name)

if __name__ == "__main__":
    raise SystemExit(main())
