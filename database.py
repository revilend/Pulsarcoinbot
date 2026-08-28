import aiosqlite
import json
from datetime import datetime

DB_NAME = "pulsar_bot.db"

async def init_db():
    """Ma'lumotlar bazasi jadvallarini yaratish"""
    async with aiosqlite.connect(DB_NAME) as db:
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
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                reward_plsr INTEGER,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0
            )
        """)
        await db.commit()

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

async def add_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def add_gems(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET quasar_gems = quasar_gems + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def get_referral_count(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else 0

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

async def export_all_data_json() -> str:
    """Barcha foydalanuvchilar va promo-kodlarni JSON faylga eksport qilish"""
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
    """JSON formatidagi backup ma'lumotlarini bazaga tiklash (restore)"""
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

async def create_promo_code(code: str, reward_plsr: int, max_uses: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO promo_codes (code, reward_plsr, max_uses, used_count)
            VALUES (?, ?, ?, 0)
        """, (code.upper(), reward_plsr, max_uses))
        await db.commit()
