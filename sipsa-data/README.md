# Baskio

Este paquete contiene la capa de datos SIPSA y el bot de Telegram **Baskio**. El
bot usa una sola cuenta y permite que cada persona se identifique libremente
como **consumidor** o **negocio pequeño**; no hay autenticación ni control de
perfil en esta versión.

## Configurar el bot de Telegram

1. Abre el chat oficial [`@BotFather`](https://t.me/BotFather) y ejecuta
   `/newbot`.
2. Usa `Baskio` como nombre visible.
3. Elige un nombre de usuario único que termine en `bot`, por ejemplo
   `BaskioColBot` o `BaskioPreciosBot` si están disponibles.
4. Copia la configuración local:

   ```powershell
   Copy-Item .env.example .env
   ```

5. Abre `.env` en tu equipo y pega el token únicamente en esta variable:

   ```dotenv
   TELEGRAM_BOT_TOKEN=pega_aqui_el_token_entregado_por_BotFather
   ```

El archivo `.env` está ignorado por Git. No pegues el token en chats, commits,
capturas, documentación ni registros de ejecución. Si se expone, revócalo desde
`@BotFather` y genera uno nuevo.

## Ejecutar en modo demo

El modo predeterminado usa fixtures locales y no depende del backend:

```powershell
python -m pip install -e ".[dev]"
python -m sipsa.telegram_bot
```

Las respuestas simuladas se identifican con
`🧪 Modo demo · datos simulados`. El estado mínimo de cada chat (perfil, ciudad
y último menú) se guarda en `data/ui_state.sqlite`.

## Conectar el backend cuando esté listo

Modifica solo estas variables en `.env`; los handlers y menús no cambian:

```dotenv
TELEGRAM_DATA_MODE=api
TELEGRAM_API_BASE_URL=http://127.0.0.1:8000
```

En modo API, un error de red o contrato se muestra como indisponibilidad; nunca
se sustituye silenciosamente por datos demo.

## Verificar sin tráfico real

```powershell
python -m pytest tests/test_telegram_ui.py tests/test_ui_contract.py -p no:cacheprovider
```

Las pruebas construyen la aplicación y simulan las conversaciones sin iniciar
long polling ni enviar mensajes a Telegram.
