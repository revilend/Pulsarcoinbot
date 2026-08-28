import os

# Telegram Bot Token (BotFather'dan olingan token)
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKENINGIZNI_BU_YERGA_YOZING")

# Mini App WebApp URL manzili (Vercel, GitHub Pages yoki Render URL)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://sizning-saytingiz.vercel.app")

# Render tashqi manzili (Self-ping uchun)
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://pulsar-tap-bot.onrender.com")

# Adminlarning Telegram ID raqamlari (@userinfobot orqali olishingiz mumkin)
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "123456789").split(",") if i.strip().isdigit()]

# Majburiy a'zo bo'lishi kerak bo'lgan kanallar
# Diqqat: Bot ushbu kanallarda ADMIN bo'lishi shart!
CHANNELS = [
    {
        "id": "@pulsar_news",
        "name": "Pulsar Rasmiy Kanal",
        "url": "https://t.me/pulsar_news"
    },
    {
        "id": "@pulsar_community",
        "name": "Pulsar Hamjamiyati",
        "url": "https://t.me/pulsar_community"
    }
]

# Bonuslar miqdori ($PLSR)
START_BONUS = 500
REFERRAL_BONUS_REGULAR = 5000
REFERRAL_BONUS_PREMIUM = 15000
