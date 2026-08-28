import aiosqlite
import json
from datetime import datetime

DB_NAME = "pulsar_bot.db"

async def init_db():
    """Ma'lumotlar bazasi jadvallarini yaratish"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Asosiy foydalanuvchilar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 500,
                quasar_gems INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 100,
                max_energy INTEGER DEFAULT 100,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                referred_by INTEGER,
                is_verified INTEGER DEFAULT 0,
                daily_streak INTEGER DEFAULT 0,
                last_daily_claim TEXT DEFAULT '',
                created_at TEXT
            )
        """)
        # Promo-kodlar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                reward_plsr INTEGER,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0
            )
        """)
        # Promo-kod ishlatilishi
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                code TEXT,
                used_at TEXT,
                UNIQUE(user_id, code)
            )
        """)
        # Kanallar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL
            )
        """)
        # Global chat xabarlari
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                text TEXT,
                created_at TEXT
            )
        """)
        # Spin tarixi (cooldown uchun)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS spin_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prize TEXT,
                prize_amount INTEGER,
                spun_at TEXT
            )
        """)
        # Mining binolari (har bir foydalanuvchining sotib olgan generatorlari)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_mining (
                user_id INTEGER,
                building_id INTEGER,
                level INTEGER DEFAULT 0,
                PRIMARY KEY(user_id, building_id)
            )
        """)
        # Rate limiting (anticheat)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit (
                user_id INTEGER,
                action TEXT,
                count INTEGER DEFAULT 0,
                window_start TEXT,
                UNIQUE(user_id, action)
            )
        """)
        # Gem transfer (P2P) tarixi
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gem_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                amount INTEGER,
                transferred_at TEXT
            )
        """)
        # Exchange tarixi
        await db.execute("""
            CREATE TABLE IF NOT EXISTS exchange_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plsr_amount INTEGER,
                gems_received INTEGER,
                exchanged_at TEXT
            )
        """)
        await db.commit()

# ============ FOYDALANUVCHI ============

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def get_user_by_username(username: str):
    clean_username = username.lstrip("@").lower()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE LOWER(username) = ?", (clean_username,)) as cursor:
            return await cursor.fetchone()

async def get_user_by_id_str(id_str: str):
    """ID string bo'lganda foydalanuvchini topish"""
    if id_str.isdigit():
        return await get_user(int(id_str))
    return await get_user_by_username(id_str)

async def add_user(user_id: int, username: str, full_name: str, referred_by: int = None, start_bonus: int = 500):
    async with aiosqlite.connect(DB_NAME) as db:
        created_at = datetime.now().isoformat()
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name, balance, referred_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, full_name, start_bonus, referred_by, created_at))
        await db.commit()

async def set_user_verified(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def update_user_balance(user_id: int, balance: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance, user_id))
        await db.commit()

async def add_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def spend_balance(user_id: int, amount: int) -> bool:
    """Balansdan xarajat qilish — yetarli bo'lsa True qaytaradi"""
    user = await get_user(user_id)
    if not user or user['balance'] < amount:
        return False
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        await db.commit()
    return True

async def add_gems(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET quasar_gems = quasar_gems + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def spend_gems(user_id: int, amount: int) -> bool:
    user = await get_user(user_id)
    if not user or user['quasar_gems'] < amount:
        return False
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET quasar_gems = quasar_gems - ? WHERE user_id = ?", (amount, user_id))
        await db.commit()
    return True

async def update_user_energy(user_id: int, energy: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET energy = ? WHERE user_id = ?", (energy, user_id))
        await db.commit()

async def update_user_xp(user_id: int, xp: int, level: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (xp, level, user_id))
        await db.commit()

# ============ REFERRAL ============

async def get_referral_count(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else 0

# ============ STATISTIKA ============

async def get_total_users_count():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            res = await cursor.fetchone()
            return res[0] if res else 0

async def get_total_economy():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT SUM(balance), SUM(quasar_gems) FROM users") as cursor:
            res = await cursor.fetchone()
            return res[0] or 0, res[1] or 0

async def get_all_user_ids():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

# ============ LEADERBOARD ============

async def get_leaderboard(limit: int = 50):
    """Haqiqiy reyting — bazadan top balansli o'yinchilar"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, full_name, balance FROM users ORDER BY balance DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_user_rank(user_id: int):
    """Foydalanuvchining umumiy reytdagi o'rni"""
    user = await get_user(user_id)
    if not user:
        return 0
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE balance > ?", (user['balance'],)
        ) as cursor:
            res = await cursor.fetchone()
            return (res[0] if res else 0) + 1

# ============ DAILY STREAK ============

STREAK_REWARDS = [1000, 2000, 3000, 4000, 5000, 6000, 10000]

async def claim_daily(user_id: int) -> dict:
    """Kunlik mukofot olish — natija: {success, reward, streak, error}"""
    user = await get_user(user_id)
    if not user:
        return {"success": False, "error": "Foydalanuvchi topilmadi"}

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    last_claim = user['last_daily_claim'] or ''

    if last_claim == today:
        return {"success": False, "error": "Bugun allaqachon olindi"}

    # Ketma-ketlikni hisoblash
    from datetime import timedelta
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if last_claim == yesterday:
        new_streak = min(user['daily_streak'] + 1, 7)
    else:
        new_streak = 1

    reward = STREAK_REWARDS[new_streak - 1]

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE users SET balance = balance + ?, daily_streak = ?, last_daily_claim = ?
            WHERE user_id = ?
        """, (reward, new_streak, today, user_id))
        await db.commit()

    return {"success": True, "reward": reward, "streak": new_streak}

# ============ PROMO KODLAR ============

async def create_promo_code(code: str, reward_plsr: int, max_uses: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO promo_codes (code, reward_plsr, max_uses, used_count)
            VALUES (?, ?, ?, 0)
        """, (code.upper(), reward_plsr, max_uses))
        await db.commit()

async def use_promo_code(user_id: int, code: str) -> dict:
    """Promo-kodni ishlatish — natija: {success, reward, error}"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        # Kod mavjudligini tekshirish
        async with db.execute("SELECT * FROM promo_codes WHERE code = ?", (code.upper(),)) as cursor:
            promo = await cursor.fetchone()

        if not promo:
            return {"success": False, "error": "Promo-kod topilmadi!"}

        promo = dict(promo)
        if promo['used_count'] >= promo['max_uses']:
            return {"success": False, "error": "Promo-kod limiti tugagan!"}

        # Foydalanuvchi allaqachon ishlatganmi?
        async with db.execute(
            "SELECT id FROM promo_usage WHERE user_id = ? AND code = ?",
            (user_id, code.upper())
        ) as cursor:
            existing = await cursor.fetchone()
            if existing:
                return {"success": False, "error": "Siz bu promo-kodni allaqachon ishlatgansiz!"}

        # Qo'llash
        reward = promo['reward_plsr']
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
        await db.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?", (code.upper(),))
        await db.execute(
            "INSERT INTO promo_usage (user_id, code, used_at) VALUES (?, ?, ?)",
            (user_id, code.upper(), datetime.now().isoformat())
        )
        await db.commit()

    return {"success": True, "reward": reward}

# ============ CHAT ============

async def add_chat_message(user_id: int, username: str, text: str):
    async with aiosqlite.connect(DB_NAME) as db:
        # Eski xabarlarni tozalash (faqat oxirgi 100 ta qoldirish)
        await db.execute("""
            DELETE FROM chat_messages WHERE id NOT IN (
                SELECT id FROM chat_messages ORDER BY id DESC LIMIT 100
            )
        """)
        await db.execute(
            "INSERT INTO chat_messages (user_id, username, text, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, text, datetime.now().isoformat())
        )
        await db.commit()

async def get_chat_messages(limit: int = 50):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT username, text, created_at FROM chat_messages ORDER BY id DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

# ============ SPIN ============

SPIN_COOLDOWN_SECONDS = 4 * 3600  # 4 soat

async def can_spin(user_id: int) -> dict:
    """Spin mumkinmi?"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT spun_at FROM spin_history WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        ) as cursor:
            last = await cursor.fetchone()

    if not last:
        return {"can": True, "wait_seconds": 0}

    last_time = datetime.fromisoformat(last['spun_at'])
    now = datetime.now()
    elapsed = (now - last_time).total_seconds()

    if elapsed >= SPIN_COOLDOWN_SECONDS:
        return {"can": True, "wait_seconds": 0}
    else:
        return {"can": False, "wait_seconds": int(SPIN_COOLDOWN_SECONDS - elapsed)}

async def record_spin(user_id: int, prize: str, prize_amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO spin_history (user_id, prize, prize_amount, spun_at) VALUES (?, ?, ?, ?)",
            (user_id, prize, prize_amount, datetime.now().isoformat())
        )
        await db.commit()

# ============ MINING ============

async def get_user_mining(user_id: int) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT building_id, level FROM user_mining WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def buy_mining_level(user_id: int, building_id: int, cost: int) -> bool:
    success = await spend_balance(user_id, cost)
    if not success:
        return False
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO user_mining (user_id, building_id, level)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, building_id) DO UPDATE SET level = level + 1
        """, (user_id, building_id))
        await db.commit()
    return True

# ============ P2P TRANSFER ============

async def transfer_gems(from_user: int, to_user: int, amount: int) -> dict:
    """Kristal o'tkazish"""
    if from_user == to_user:
        return {"success": False, "error": "O'zingizga o'tkazib bo'lmaydi!"}

    # Qabul qiluvchi mavjudligini tekshirish
    recipient = await get_user(to_user)
    if not recipient:
        return {"success": False, "error": "Qabul qiluvchi topilmadi!"}

    # Yetarlilikni tekshirish
    success = await spend_gems(from_user, amount)
    if not success:
        return {"success": False, "error": "Quasar kristallari yetarli emas!"}

    await add_gems(to_user, amount)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO gem_transfers (from_user, to_user, amount, transferred_at) VALUES (?, ?, ?, ?)",
            (from_user, to_user, amount, datetime.now().isoformat())
        )
        await db.commit()

    return {"success": True}

# ============ EXCHANGE ============

EXCHANGE_RATE = 1_000_000  # 1M PLSR = 1 Quasar

async def exchange_plsr_to_gems(user_id: int, plsr_amount: int) -> dict:
    """$PLSR ni Quasarga almashtirish"""
    if plsr_amount < EXCHANGE_RATE:
        return {"success": False, "error": f"Kamida {EXCHANGE_RATE:,} $PLSR kerak!"}

    gems_to_get = plsr_amount // EXCHANGE_RATE
    actual_cost = gems_to_get * EXCHANGE_RATE

    success = await spend_balance(user_id, actual_cost)
    if not success:
        return {"success": False, "error": "Balansingiz yetarli emas!"}

    await add_gems(user_id, gems_to_get)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO exchange_history (user_id, plsr_amount, gems_received, exchanged_at) VALUES (?, ?, ?, ?)",
            (user_id, actual_cost, gems_to_get, datetime.now().isoformat())
        )
        await db.commit()

    return {"success": True, "gems_received": gems_to_get, "plsr_spent": actual_cost}

# ============ RATE LIMITING (ANTICHEAT) ============

async def check_rate_limit(user_id: int, action: str, max_count: int, window_seconds: int) -> bool:
    """Rate limit tekshirish — True = ruxsat beriladi, False = limit oshdi"""
    now = datetime.now()
    window_start = now.isoformat()

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT count, window_start FROM rate_limit WHERE user_id = ? AND action = ?",
            (user_id, action)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            row = dict(row)
            last_window = datetime.fromisoformat(row['window_start'])
            elapsed = (now - last_window).total_seconds()

            if elapsed < window_seconds:
                if row['count'] >= max_count:
                    return False  # Limit oshdi
                await db.execute(
                    "UPDATE rate_limit SET count = count + 1 WHERE user_id = ? AND action = ?",
                    (user_id, action)
                )
            else:
                # Yangi oyna boshlandi
                await db.execute(
                    "UPDATE rate_limit SET count = 1, window_start = ? WHERE user_id = ? AND action = ?",
                    (window_start, user_id, action)
                )
        else:
            await db.execute(
                "INSERT INTO rate_limit (user_id, action, count, window_start) VALUES (?, ?, 1, ?)",
                (user_id, action, window_start)
            )

        await db.commit()
    return True

# ============ BACKUP/RESTORE ============

async def export_all_data_json() -> str:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            users = [dict(row) for row in await cursor.fetchall()]
        async with db.execute("SELECT * FROM promo_codes") as cursor:
            promos = [dict(row) for row in await cursor.fetchall()]

        backup = {
            "exported_at": datetime.now().isoformat(),
            "users_count": len(users),
            "users": users,
            "promo_codes": promos
        }
        return json.dumps(backup, indent=2, ensure_ascii=False)

async def import_data_from_json(json_str: str) -> tuple[int, int]:
    data = json.loads(json_str)
    users = data.get("users", [])
    promos = data.get("promo_codes", [])

    async with aiosqlite.connect(DB_NAME) as db:
        for u in users:
            await db.execute("""
                INSERT OR REPLACE INTO users
                (user_id, username, full_name, balance, quasar_gems, energy, max_energy, level, xp, referred_by, is_verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                u.get("user_id"), u.get("username"), u.get("full_name"),
                u.get("balance", 500), u.get("quasar_gems", 0),
                u.get("energy", 100), u.get("max_energy", 100),
                u.get("level", 1), u.get("xp", 0),
                u.get("referred_by"), u.get("is_verified", 1),
                u.get("created_at", datetime.now().isoformat())
            ))
        for p in promos:
            await db.execute("""
                INSERT OR REPLACE INTO promo_codes (code, reward_plsr, max_uses, used_count)
                VALUES (?, ?, ?, ?)
            """, (p.get("code"), p.get("reward_plsr"), p.get("max_uses"), p.get("used_count", 0)))
        await db.commit()
    return len(users), len(promos)

# ============ CHANNELS ============

async def get_all_channels() -> list[dict]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM channels") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def add_channel(channel_id: str, name: str, url: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO channels (channel_id, name, url) VALUES (?, ?, ?)",
                         (channel_id, name, url))
        await db.commit()

async def remove_channel(channel_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await db.commit()

async def get_channel(channel_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM channels WHERE channel_id = ?", (channel_id,)) as cursor:
            return await cursor.fetchone()

async def get_channel_count() -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM channels") as cursor:
            res = await cursor.fetchone()
            return res[0] if res else 0
