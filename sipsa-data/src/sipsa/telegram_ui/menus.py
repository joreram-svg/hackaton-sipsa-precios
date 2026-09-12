"""Teclados de Telegram separados por tipo de usuario."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def _button(text: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback)


def profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_button("Soy consumidor", "profile:consumer")],
            [_button("Tengo un negocio pequeño", "profile:small_business")],
        ]
    )


def consumer_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _button("Precios de hoy", "consumer:today"),
                _button("Buscar producto", "consumer:search"),
            ],
            [_button("Comparar ciudades", "consumer:compare")],
            [_button("Ver cambios recientes", "consumer:recent")],
            [
                _button("Cambiar ciudad", "common:city"),
                _button("Cambiar perfil", "common:profile"),
            ],
        ]
    )


def business_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_button("Resumen del negocio", "business:summary")],
            [
                _button("Explorar productos", "business:explore"),
                _button("Mi seguimiento", "business:watchlist"),
            ],
            [_button("Comparar ciudades", "business:compare")],
            [
                _button("Preferencias", "business:preferences"),
                _button("Historial reciente", "business:history"),
            ],
            [
                _button("Cambiar ciudad", "common:city"),
                _button("Cambiar perfil", "common:profile"),
            ],
        ]
    )


def city_menu(cities: list[dict[str, object]]) -> InlineKeyboardMarkup:
    rows = [
        [_button(str(city["name"]), f"city:{city['name']}")]
        for city in cities
        if city.get("name")
    ]
    rows.append([_button("Volver al menú", "common:home")])
    return InlineKeyboardMarkup(rows)


def result_menu(*, retry: bool = False) -> InlineKeyboardMarkup:
    row = []
    if retry:
        row.append(_button("Reintentar", "common:retry"))
    row.append(_button("Volver al menú", "common:home"))
    return InlineKeyboardMarkup([row])
