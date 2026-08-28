import os

# Telegram Bot Token (BotFather'dan olingan token)
BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKENINGIZNI_BU_YERGA_YOZING")

# Mini App WebApp URL manzili
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://revilend.github.io/Pulsarcoinbot/")

# Render tashqi manzili (Self-ping uchun)
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://pulsarcoinbot.onrender.com")

# Adminlarning Telegram ID raqamlari
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "123456789").split(",") if i.strip().isdigit()]

# Bonuslar miqdori ($PLSR)
START_BONUS = 500
REFERRAL_BONUS_REGULAR = 5000
REFERRAL_BONUS_PREMIUM = 15000

# Exchange: $PLSR → Quasar kristali
EXCHANGE_RATE = 1_000_000  # 1,000,000 PLSR = 1 Quasar

# Tap sozlamalari (anticheat uchun)
TAP_ENERGY_COST = 1
MAX_TAPS_PER_SECOND = 15  # soniyada eng ko'p tap
TAP_BASE_REWARD = 1

# Spin sozlamalari
SPIN_COOLDOWN_SECONDS = 4 * 3600  # 4 soat

# Mining binolari
MINING_BUILDINGS = [
    {"id": 1, "name": "Kvant Kollektori", "base_cost": 1000, "rate": 250, "icon": "fa-microchip"},
    {"id": 2, "name": "Stellar Reaktor", "base_cost": 5000, "rate": 1200, "icon": "fa-atom"},
    {"id": 3, "name": "Kosmik Turbina", "base_cost": 20000, "rate": 5000, "icon": "fa-fan"},
    {"id": 4, "name": "Dyson Radiatori", "base_cost": 100000, "rate": 25000, "icon": "fa-sun"},
]

# Spin mukofotlari
SPIN_PRIZES = [
    {"name": "5,000 PLSR", "type": "plsr", "amount": 5000},
    {"name": "15,000 PLSR", "type": "plsr", "amount": 15000},
    {"name": "50,000 PLSR", "type": "plsr", "amount": 50000},
    {"name": "100,000 PLSR", "type": "plsr", "amount": 100000},
    {"name": "5 Quasar", "type": "gems", "amount": 5},
    {"name": "To'liq Energiya", "type": "energy", "amount": 100},
    {"name": "+500 XP", "type": "xp", "amount": 500},
    {"name": "25,000 PLSR", "type": "plsr", "amount": 25000},
]
