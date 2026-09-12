"""Recorridos conversacionales del bot, independientes de la fuente de datos."""

from __future__ import annotations

import logging
from typing import Any

from sipsa.telegram_ui.data_provider import DataUnavailable, UiPayload
from sipsa.telegram_ui.menus import (
    business_menu,
    city_menu,
    consumer_menu,
    profile_menu,
    result_menu,
)
from sipsa.telegram_ui.state import PreferenceStore, UserProfile

logger = logging.getLogger(__name__)

PRODUCT_NAME = "Baskio"
DEMO_LABEL = "🧪 Modo demo · datos simulados"
DEFAULT_PRODUCT_ID = "tomate-chonto"


def _dependencies(context: Any) -> tuple[PreferenceStore, Any]:
    data = context.application.bot_data
    return data["store"], data["provider"]


def _home(profile: UserProfile, city: str) -> tuple[str, Any]:
    if profile is UserProfile.CONSUMER:
        text = (
            f"{PRODUCT_NAME} · Consumidor\nCiudad: {city}\n\n"
            "Precios de hoy · Buscar producto\n"
            "Comparar ciudades · Ver cambios recientes"
        )
        return text, consumer_menu()
    text = (
        f"{PRODUCT_NAME} · Negocio pequeño\nCiudad: {city}\n\n"
        "Resumen del negocio · Explorar productos\n"
        "Mi seguimiento · Comparar ciudades\n"
        "Preferencias · Historial reciente"
    )
    return text, business_menu()


def _payload_text(payload: UiPayload) -> str:
    return f"{DEMO_LABEL}\n\n{payload.text}" if payload.demo else payload.text


async def start(update: Any, context: Any) -> None:
    store, _ = _dependencies(context)
    preferences = store.get(update.effective_chat.id)
    if preferences.profile is None:
        await update.message.reply_text(
            f"¡Hola! Soy {PRODUCT_NAME}.\n\n¿Cómo usarás el servicio?",
            reply_markup=profile_menu(),
        )
        return
    text, markup = _home(preferences.profile, preferences.city)
    await update.message.reply_text(text, reply_markup=markup)


async def select_profile(update: Any, context: Any) -> None:
    store, _ = _dependencies(context)
    query = update.callback_query
    await query.answer()
    value = query.data.removeprefix("profile:")
    try:
        profile = UserProfile(value)
    except ValueError:
        await query.edit_message_text(
            "No reconocimos ese perfil. Elige una opción.", reply_markup=profile_menu()
        )
        return
    store.set_profile(update.effective_chat.id, profile)
    store.set_last_menu(update.effective_chat.id, "home")
    preferences = store.get(update.effective_chat.id)
    text, markup = _home(profile, preferences.city)
    await query.edit_message_text(text, reply_markup=markup)


async def change_profile(update: Any, context: Any) -> None:
    text = "¿Cómo usarás el servicio? Puedes cambiarlo cuando quieras."
    if update.callback_query is not None and update.callback_query.data:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=profile_menu())
    else:
        await update.message.reply_text(text, reply_markup=profile_menu())


async def show_home(update: Any, context: Any) -> None:
    store, _ = _dependencies(context)
    preferences = store.get(update.effective_chat.id)
    if preferences.profile is None:
        await change_profile(update, context)
        return
    text, markup = _home(preferences.profile, preferences.city)
    if update.callback_query is not None and update.callback_query.data:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def select_city(update: Any, context: Any) -> None:
    store, _ = _dependencies(context)
    query = update.callback_query
    await query.answer()
    city = query.data.removeprefix("city:").strip()
    if not city:
        await query.edit_message_text(
            "No reconocimos la ciudad.", reply_markup=result_menu(retry=True)
        )
        return
    store.set_city(update.effective_chat.id, city)
    preferences = store.get(update.effective_chat.id)
    if preferences.profile is None:
        await query.edit_message_text(
            "Ciudad guardada. Ahora elige tu perfil.", reply_markup=profile_menu()
        )
        return
    text, markup = _home(preferences.profile, preferences.city)
    await query.edit_message_text(f"Ciudad actualizada.\n\n{text}", reply_markup=markup)


async def _run_data_action(action: str, preferences: Any, provider: Any) -> UiPayload:
    if action == "consumer:today":
        return await provider.summary(preferences.city, "consumer")
    if action == "business:summary":
        return await provider.summary(preferences.city, "small_business")
    if action in {"consumer:compare", "business:compare"}:
        return await provider.compare_cities(DEFAULT_PRODUCT_ID)
    if action in {"consumer:recent", "business:history"}:
        return await provider.trend(DEFAULT_PRODUCT_ID, preferences.city)
    raise DataUnavailable("Esta opción aún no tiene una fuente de datos")


async def handle_action(update: Any, context: Any) -> None:
    store, provider = _dependencies(context)
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "common:home":
        preferences = store.get(update.effective_chat.id)
        if preferences.profile is None:
            await query.edit_message_text(
                "¿Cómo usarás el servicio?", reply_markup=profile_menu()
            )
            return
        text, markup = _home(preferences.profile, preferences.city)
        await query.edit_message_text(text, reply_markup=markup)
        return
    if action == "common:profile":
        await query.edit_message_text(
            "¿Cómo usarás el servicio? Puedes cambiarlo cuando quieras.",
            reply_markup=profile_menu(),
        )
        return

    preferences = store.get(update.effective_chat.id)
    if action == "common:retry":
        action = preferences.last_menu
    if action == "awaiting_search":
        await query.edit_message_text(
            "Escribe nuevamente el nombre del producto.",
            reply_markup=result_menu(),
        )
        return
    if action == "common:city":
        store.set_last_menu(update.effective_chat.id, action)
        try:
            payload = await provider.list_cities()
            cities = payload.metadata.get("cities", [])
            await query.edit_message_text(
                _payload_text(payload), reply_markup=city_menu(cities)
            )
        except DataUnavailable:
            await query.edit_message_text(
                "No pudimos cargar las ciudades. Intenta nuevamente.",
                reply_markup=result_menu(retry=True),
            )
        return
    if action in {"consumer:search", "business:explore"}:
        store.set_last_menu(update.effective_chat.id, "awaiting_search")
        await query.edit_message_text(
            "Escribe el nombre del producto que quieres buscar.",
            reply_markup=result_menu(),
        )
        return
    if action == "business:watchlist":
        payload = UiPayload(
            "Mi seguimiento\n• Tomate chonto\n• Papa pastusa\n• Plátano hartón",
            demo=True,
        )
        await query.edit_message_text(_payload_text(payload), reply_markup=result_menu())
        return
    if action == "business:preferences":
        payload = UiPayload(
            f"Preferencias\n• Ciudad: {preferences.city}\n• Perfil: Negocio pequeño",
            demo=True,
        )
        await query.edit_message_text(_payload_text(payload), reply_markup=result_menu())
        return

    store.set_last_menu(update.effective_chat.id, action)
    try:
        payload = await _run_data_action(action, preferences, provider)
    except DataUnavailable:
        await query.edit_message_text(
            "Los datos no están disponibles en este momento.",
            reply_markup=result_menu(retry=True),
        )
    except Exception as error:  # Protección de la conversación ante fallos imprevistos.
        logger.error("Fallo inesperado del proveedor: %s", type(error).__name__)
        await query.edit_message_text(
            "Ocurrió un problema al mostrar esta opción.",
            reply_markup=result_menu(retry=True),
        )
    else:
        await query.edit_message_text(_payload_text(payload), reply_markup=result_menu())


async def search_message(update: Any, context: Any) -> None:
    store, provider = _dependencies(context)
    preferences = store.get(update.effective_chat.id)
    if preferences.last_menu != "awaiting_search":
        await update.message.reply_text(
            "Usa el menú para elegir una opción.", reply_markup=result_menu()
        )
        return
    try:
        payload = await provider.search_products(update.message.text or "")
    except DataUnavailable:
        await update.message.reply_text(
            "No pudimos completar la búsqueda.", reply_markup=result_menu(retry=True)
        )
        return
    store.set_last_menu(update.effective_chat.id, "home")
    await update.message.reply_text(_payload_text(payload), reply_markup=result_menu())
