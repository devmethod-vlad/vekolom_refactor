from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider

from app.ioc.providers import (
    DatabaseProvider,
    HomeProvider,
    SettingsProvider,
    TemplatesProvider,
)


def build_container():
    # FastapiProvider нужен, если будешь инжектить Request/WebSocket в фабрики провайдера :contentReference[oaicite:5]{index=5}
    return make_async_container(
        SettingsProvider(),
        DatabaseProvider(),
        TemplatesProvider(),
        HomeProvider(),
        FastapiProvider(),
    )
