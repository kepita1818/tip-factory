# Futbol Analyzer Bot

Bot de Telegram para analisis estadistico de partidos de futbol.

## Deploy en Render

1. Crea un repositorio en GitHub con estos 3 archivos
2. Conecta el repo a Render (New Web Service -&gt; Build and deploy from a Git repository)
3. En Render, selecciona:
   - **Language**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn bot:app`
4. Configura Environment Variables:
   - `API_FOOTBALL_KEY` = tu_api_key_de_football-data.org
   - `TELEGRAM_BOT_TOKEN` = tu_token_de_botfather
5. Deploy
6. Visita `https://tu-app.onrender.com/set-webhook` para activar el webhook

## Comandos del Bot

- /start - Iniciar bot
- /analizar Equipo1 vs Equipo2 - Analizar partido
- /hoy - Partidos de hoy
- /ligas - Ligas disponibles
- /ayuda - Ayuda

## APIs usadas

- football-data.org v4 (datos de partidos)
- Telegram Bot API
