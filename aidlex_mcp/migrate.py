"""Explicit idempotent schema creation for controlled production migrations."""
from .config import Settings
from .store import Store
from .service import Service

def main():
    settings=Settings()
    store=Store(settings.database_url.get_secret_value(),settings.database_schema)
    store.initialize()
    Service(settings,store).seed_internal_knowledge()
    print('Aidlex MCP schema and internal research map initialized. No private case reports were imported.')
    store.engine.dispose()

if __name__=='__main__': main()
