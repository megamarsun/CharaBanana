"""Entry point for the CharaBanana application."""

from __future__ import annotations

from charabanana.api_client import NanoBananaClient
from charabanana.app import CharaBananaApp
from charabanana.environment import initialise_environment
from charabanana.storage import DataStore


def main() -> None:
    paths = initialise_environment()
    datastore = DataStore(paths)
    client = NanoBananaClient(datastore, paths)
    app = CharaBananaApp(datastore, client)
    app.run()


if __name__ == "__main__":
    main()
