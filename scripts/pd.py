"""Project entrypoint for pinned Paradigma with Filum version-path support."""
from paradigma_adapter import install

install()
from paradigma.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
