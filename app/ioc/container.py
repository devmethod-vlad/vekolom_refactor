from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider

from app.ioc.providers import (
    ApiKeysProvider,
    ContactsProvider,
    DatabaseProvider,
    HomeProvider,
    PricelistProvider,
    SettingsProvider,
    TemplatesProvider,
    UoWProvider,
)


def build_container():
    # FastapiProvider нужен, если будешь инжектить Request/WebSocket в фабрики провайдера
    return make_async_container(
        SettingsProvider(),
        DatabaseProvider(),
        TemplatesProvider(),
        HomeProvider(),
        PricelistProvider(),
        ContactsProvider(),
        ApiKeysProvider(),
        UoWProvider(),
        FastapiProvider(),
    )
