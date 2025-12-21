import logging

def setup_logging(debug: bool = False) -> None:
    """
    Базовая настройка логирования.

    Почему тут:
    - это часть инфраструктуры приложения
    - вызывается один раз при старте
    - не размазана по модулям (bootstrap и т.п.)
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)-5s [%(name)s] %(message)s",
    )
