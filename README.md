# ⚡ Pulsar Tap-to-Earn Telegram Bot & Mini App

Ushbu loyiha **Telegram Bot** va **Telegram Mini App (TWA)** ekotizimi uchun to'liq tayyorlangan starter paketdir.

## 🚀 Loyiha tarkibi:
- `bot.py` — Asosiy bot fayli (aiogram 3.x, obuna tekshiruvi, aiohttp web-server va Keep-Alive self-ping).
- `admin.py` — Admin paneli (statistika, barcha o'yinchilarga xabar tarqatish/rassilka, promo-kod yaratish).
- `database.py` — Asinxron SQLite ma'lumotlar bazasi.
- `config.py` — Bot tokeni, homiy kanallar va bonuslar sozlamasi.
- `webapp/index.html` — Mini App (TWA) kosmik uslubdagi Tap-to-Earn frontend qismi.
- `requirements.txt`, `Procfile`, `runtime.txt` — Render va GitHub uchun tayyor deploy konfiguratsiyasi.

## 🛠 GitHub va Renderga joylash bo'yicha qo'llanma:

1. **GitHub'ga yuklash:**
   - Ushbu fayllarni yangi GitHub repository'ga yuklang (`git push`).

2. **Render.com da yangi Web Service ochish:**
   - [Render.com](https://render.com) ga kiring va **New +** -> **Web Service** ni tanlang.
   - GitHub repository'ingizni ulang.
   - Sozlamalar:
     - **Runtime:** `Python 3`
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python bot.py`
     - **Environment Variables:**
       - `BOT_TOKEN` = Sizning bot tokeningiz
       - `ADMIN_IDS` = Sizning Telegram ID raqamingiz
       - `RENDER_EXTERNAL_URL` = Render beradigan havola (masalan: `https://pulsar-tap-bot.onrender.com`)
       - `WEBAPP_URL` = Mini App joylangan havola

3. **Auto-Ping (UptimeRobot):**
   - [UptimeRobot.com](https://uptimerobot.com) saytida yangi HTTP monitor oching va `https://sizning-app.onrender.com/ping` manzilini har 5 daqiqaga qo'ying.
