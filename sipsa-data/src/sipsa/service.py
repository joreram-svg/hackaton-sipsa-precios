from sipsa.db.repo import Repository


def build_weekly_summary(repo: Repository, ciudad: str = "Bogotá", perfil: str = "consumidor") -> dict:
    """Compone el resumen compartido por REST, MCP, snapshot y Telegram."""
    buy = repo.opportunities(ciudad, None, perfil, 5, False)
    avoid = repo.opportunities(ciudad, None, perfil, 5, True)
    alert_data = repo.alerts(ciudad, 15, "1w")
    buy_names = ", ".join(item["nombre"] for item in buy["items"])
    avoid_names = ", ".join(item["nombre"] for item in avoid["items"])
    text = f"📊 SIPSA {ciudad}: ↑ Comprar: {buy_names}. ↓ Evitar: {avoid_names}."
    if alert_data["alertas"]:
        first = alert_data["alertas"][0]
        text += f" Alerta: {first['nombre']} {first['direccion'].lower()} {abs(first['var_pct']) * 100:.0f}%."
    return {
        "fecha": buy["fecha"],
        "ciudad": ciudad,
        "perfil": perfil,
        "top_comprar": buy["items"],
        "top_evitar": avoid["items"],
        "alertas": alert_data["alertas"],
        "texto": text[:600],
    }
