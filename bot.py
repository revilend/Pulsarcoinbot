import os
import asyncio
import logging
import json
import hashlib
import hmac
import time
import random
import math
from urllib.parse import urlparse, parse_qs
from datetime import datetime

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, WebAppInfo
)
from aiogram.enums import ChatMemberStatus

import config
import database as db
from admin import admin_router

logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()
dp.include_router(admin_router)

# ============ TELEGRAM WEBAPP AUTH ============

def validate_tg_init_data(init_data: str, bot_token: str) -> dict | None:
    """Telegram WebApp initData ni tekshirish — haqiqiy foydalanuvchi ekanligini tasdiqlash"""
    try:
        parsed = parse_qs(init_data)
        data_check_string_parts = []
        user_data = None

        for key, values in sorted(parsed.items()):
            if key == "hash":
                continue
            data_check_string_parts.append(f"{key}={values[0]}")
            if key == "user":
                user_data = json.loads(values[0])

        data_check_string = "\n".join(data_check_string_parts)

        # HMAC-SHA256
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if computed_hash != parsed.get("hash", [""])[0]:
            return None

        return user_data
    except Exception as e:
        logging.error(f"InitData validation error: {e}")
        return None

# ============ WEB SERVER ============

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

async def handle_index(request):
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return web.FileResponse(index_path, content_type="text/html")
    return web.Response(text="Not found", status=404)

async def handle_css(request):
    css_path = os.path.join(BASE_DIR, "style.css")
    if os.path.exists(css_path):
        return web.FileResponse(css_path, content_type="text/css")
    return web.Response(status=404)

async def handle_js(request):
    js_path = os.path.join(BASE_DIR, "app.js")
    if os.path.exists(js_path):
        return web.FileResponse(js_path, content_type="application/javascript")
    return web.Response(status=404)

async def handle_ping(request):
    return web.Response(text="Pulsar Bot is running alive!", status=200)

# ============ API ENDPOINTLAR ============

async def api_get_user(request):
    """Foydalanuvchi ma'lumotlarini olish"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"error": "Auth failed"}, status=401)

        user_id = int(user_data["id"])
        user = await db.get_user(user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        # Passive income hisoblash
        mining = await db.get_user_mining(user_id)
        passive_per_hour = sum(
            b['level'] * config.MINING_BUILDINGS[b['building_id'] - 1]['rate']
            for b in mining if b['building_id'] <= len(config.MINING_BUILDINGS)
        )

        return web.json_response({
            "user_id": user_id,
            "username": user['username'] or "",
            "full_name": user['full_name'] or "O'yinchi",
            "balance": user['balance'],
            "quasar_gems": user['quasar_gems'],
            "energy": user['energy'],
            "max_energy": user['max_energy'],
            "level": user['level'],
            "xp": user['xp'],
            "passive_per_hour": passive_per_hour,
            "daily_streak": user['daily_streak'],
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_tap(request):
    """Tap event — backendda hisoblaydi, anticheat bilan"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        client_taps = data.get("taps", 1)  # Necha marta bosilgani

        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"error": "Auth failed"}, status=401)

        user_id = int(user_data["id"])
        user = await db.get_user(user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        # Rate limiting — soniyada 15 tadan ortiq tap rad etiladi
        if not await db.check_rate_limit(user_id, "tap", config.MAX_TAPS_PER_SECOND, 1):
            return web.json_response({"error": "Rate limit exceeded", "balance": user['balance']}, status=429)

        # Energiya tekshirish
        available_taps = min(client_taps, user['energy'])
        if available_taps <= 0:
            return web.json_response({"error": "No energy", "balance": user['balance'], "energy": 0}, status=400)

        # Daromad hisoblash (combo brauzer tomonidan boshqariladi, lekin server ham tekshiradi)
        earned = available_taps  # 1 tap = 1 PLSR (bazaviy)
        new_energy = max(0, user['energy'] - available_taps)
        new_balance = user['balance'] + earned
        new_xp = user['xp'] + earned
        new_level = user['level']

        # Level up check
        xp_needed = 100 * (1.8 ** (new_level - 1))
        while new_xp >= xp_needed and new_level < 20:
            new_xp -= int(xp_needed)
            new_level += 1
            xp_needed = 100 * (1.8 ** (new_level - 1))

        # Bazaga yozish
        await db.update_user_balance(user_id, new_balance)
        await db.update_user_energy(user_id, new_energy)
        await db.update_user_xp(user_id, new_xp, new_level)

        return web.json_response({
            "balance": new_balance,
            "energy": new_energy,
            "xp": new_xp,
            "level": new_level,
            "earned": earned,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_leaderboard(request):
    """Haqiqiy reyting — bazadan"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        user_id = int(user_data["id"]) if user_data else 0

        leaders = await db.get_leaderboard(50)
        my_rank = await db.get_user_rank(user_id) if user_id else 0

        return web.json_response({
            "leaders": leaders,
            "my_rank": my_rank,
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_spin(request):
    """Spin — backend RNG, 4 soatlik cooldown"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"error": "Auth failed"}, status=401)

        user_id = int(user_data["id"])
        user = await db.get_user(user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        # Cooldown tekshirish
        spin_check = await db.can_spin(user_id)
        if not spin_check['can']:
            return web.json_response({
                "error": "Cooldown",
                "wait_seconds": spin_check['wait_seconds']
            }, status=429)

        # Server-side RNG
        prize = random.choice(config.SPIN_PRIZES)
        prize_type = prize['type']
        prize_amount = prize['amount']

        # Mukofotni qo'llash
        if prize_type == "plsr":
            await db.add_balance(user_id, prize_amount)
        elif prize_type == "gems":
            await db.add_gems(user_id, prize_amount)
        elif prize_type == "energy":
            await db.update_user_energy(user_id, user['max_energy'])
        elif prize_type == "xp":
            new_xp = user['xp'] + prize_amount
            new_level = user['level']
            xp_needed = 100 * (1.8 ** (new_level - 1))
            while new_xp >= xp_needed and new_level < 20:
                new_xp -= int(xp_needed)
                new_level += 1
                xp_needed = 100 * (1.8 ** (new_level - 1))
            await db.update_user_xp(user_id, new_xp, new_level)

        # Tarixga yozish
        await db.record_spin(user_id, prize['name'], prize_amount)

        # Yangilangan foydalanuvchi
        updated_user = await db.get_user(user_id)

        return web.json_response({
            "prize_name": prize['name'],
            "prize_type": prize_type,
            "prize_amount": prize_amount,
            "balance": updated_user['balance'],
            "gems": updated_user['quasar_gems'],
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_spin_status(request):
    """Spin holati — qachon keyingi spin mumkin"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"can": True, "wait_seconds": 0})

        user_id = int(user_data["id"])
        result = await db.can_spin(user_id)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"can": True, "wait_seconds": 0})

async def api_chat(request):
    """Chat xabarlarini olish"""
    try:
        messages = await db.get_chat_messages(50)
        return web.json_response({"messages": messages})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_chat_send(request):
    """Chatga xabar yuborish"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        text = data.get("text", "").strip()[:500]  # Maks 500 belgi

        if not text:
            return web.json_response({"error": "Empty message"}, status=400)

        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"error": "Auth failed"}, status=401)

        user_id = int(user_data["id"])

        # Rate limit — minutiga 10 xabar
        if not await db.check_rate_limit(user_id, "chat", 10, 60):
            return web.json_response({"error": "Rate limit: minutiga 10 xabar"}, status=429)

        username = user_data.get("username", "O'yinchi")
        await db.add_chat_message(user_id, username, text)
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_promo(request):
    """Promo-kod ishlatish"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        code = data.get("code", "").strip().upper()

        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"error": "Auth failed"}, status=401)

        if not code:
            return web.json_response({"error": "Kod kiriting"}, status=400)

        user_id = int(user_data["id"])
        result = await db.use_promo_code(user_id, code)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_p2p(request):
    """P2P kristal o'tkazish"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        target = data.get("target", "").strip()
        amount = data.get("amount", 0)

        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"error": "Auth failed"}, status=401)

        if not target or amount <= 0:
            return web.json_response({"error": "Noto'g'ri ma'lumot"}, status=400)

        user_id = int(user_data["id"])

        # Rate limit — soatiga 10 o'tkazma
        if not await db.check_rate_limit(user_id, "p2p", 10, 3600):
            return web.json_response({"error": "Rate limit: soatiga 10 o'tkazma"}, status=429)

        # Target foydalanuvchini topish
        target_user = await db.get_user_by_id_str(target)
        if not target_user:
            return web.json_response({"error": "Qabul qiluvchi topilmadi!"}, status=404)

        result = await db.transfer_gems(user_id, target_user['user_id'], amount)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_exchange(request):
    """$PLSR → Quasar almashtirish"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        plsr_amount = data.get("amount", 0)

        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"error": "Auth failed"}, status=401)

        user_id = int(user_data["id"])
        result = await db.exchange_plsr_to_gems(user_id, plsr_amount)

        if result['success']:
            updated_user = await db.get_user(user_id)
            result['balance'] = updated_user['balance']
            result['gems'] = updated_user['quasar_gems']

        return web.json_response(result)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_mining(request):
    """Mining binolarini olish va sotib olish"""
    try:
        data = await request.json()
        init_data = data.get("init_data")
        action = data.get("action", "get")
        building_id = data.get("building_id", 0)

        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"error": "Auth failed"}, status=401)

        user_id = int(user_data["id"])

        if action == "get":
            user_mining = await db.get_user_mining(user_id)
            buildings = []
            for b in config.MINING_BUILDINGS:
                owned = next((m for m in user_mining if m['building_id'] == b['id']), None)
                level = owned['level'] if owned else 0
                cost = int(b['base_cost'] * (1.5 ** level))
                buildings.append({
                    "id": b['id'],
                    "name": b['name'],
                    "rate": b['rate'],
                    "icon": b['icon'],
                    "level": level,
                    "cost": cost,
                })
            return web.json_response({"buildings": buildings})

        elif action == "buy":
            if building_id < 1 or building_id > len(config.MINING_BUILDINGS):
                return web.json_response({"error": "Noto'g'ri bino"}, status=400)

            b = config.MINING_BUILDINGS[building_id - 1]
            user_mining = await db.get_user_mining(user_id)
            owned = next((m for m in user_mining if m['building_id'] == building_id), None)
            level = owned['level'] if owned else 0
            cost = int(b['base_cost'] * (1.5 ** level))

            success = await db.buy_mining_level(user_id, building_id, cost)
            if not success:
                return web.json_response({"error": "Balans yetarli emas!"}, status=400)

            updated_user = await db.get_user(user_id)
            return web.json_response({
                "success": True,
                "balance": updated_user['balance'],
                "new_level": level + 1,
                "new_cost": int(b['base_cost'] * (1.5 ** (level + 1))),
            })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_energy_regen(request):
    """Energiya tiklash"""
    try:
        data = await request.json()
        init_data = data.get("init_data")

        user_data = validate_tg_init_data(init_data, config.BOT_TOKEN)
        if not user_data:
            return web.json_response({"error": "Auth failed"}, status=401)

        user_id = int(user_data["id"])
        user = await db.get_user(user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)

        if user['energy'] < user['max_energy']:
            new_energy = min(user['energy'] + 1, user['max_energy'])
            await db.update_user_energy(user_id, new_energy)
            return web.json_response({"energy": new_energy})

        return web.json_response({"energy": user['energy']})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

# ============ WEB SERVER STARTUP ============

async def start_web_server():
    app = web.Application()

    # Statik fayllar
    app.router.add_get("/", handle_index)
    app.router.add_get("/style.css", handle_css)
    app.router.add_get("/app.js", handle_js)
    app.router.add_get("/ping", handle_ping)

    # API endpointlar
    app.router.add_post("/api/user", api_get_user)
    app.router.add_post("/api/tap", api_tap)
    app.router.add_post("/api/leaderboard", api_leaderboard)
    app.router.add_post("/api/spin", api_spin)
    app.router.add_post("/api/spin_status", api_spin_status)
    app.router.add_get("/api/chat", api_chat)
    app.router.add_post("/api/chat/send", api_chat_send)
    app.router.add_post("/api/promo", api_promo)
    app.router.add_post("/api/p2p", api_p2p)
    app.router.add_post("/api/exchange", api_exchange)
    app.router.add_post("/api/mining", api_mining)
    app.router.add_post("/api/energy", api_energy_regen)

    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server {port}-portda ishga tushdi.")

# ============ KEEP-ALIVE SELF PING ============

async def keep_alive_self_ping():
    await asyncio.sleep(30)
    ping_url = f"{config.RENDER_EXTERNAL_URL.rstrip('/')}/ping"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(ping_url) as response:
                    if response.status == 200:
                        logging.info(f"Self-ping muvaffaqiyatli: {ping_url}")
            except Exception as e:
                logging.error(f"Self-ping xatoligi: {e}")
            await asyncio.sleep(600)

# ============ BOT COMMANDS ============

async def check_user_subscriptions(user_id: int) -> bool:
    channels = await db.get_all_channels()
    if not channels:
        return True
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel["channel_id"], user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                return False
        except Exception as e:
            logging.error(f"Kanal tekshirish xatoligi ({channel['channel_id']}): {e}")
            return False
    return True

async def get_subscription_keyboard() -> InlineKeyboardMarkup:
    channels = await db.get_all_channels()
    buttons = []
    for i, ch in enumerate(channels, start=1):
        buttons.append([InlineKeyboardButton(text=f"📢 {ch['name']} #{i}", url=ch["url"])])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish (Verify)", callback_data="verify_subs")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 O'yinni Boshlash (Play $PLSR)",
                    web_app=WebAppInfo(url=config.WEBAPP_URL)
                )
            ],
            [
                InlineKeyboardButton(text="👥 Do'stlarni taklif qilish", callback_data="referrals")
            ]
        ]
    )

@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or "O'yinchi"

    referrer_id = None
    if command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args.replace("ref_", ""))
            if referrer_id == user_id:
                referrer_id = None
        except ValueError:
            referrer_id = None

    existing_user = await db.get_user(user_id)
    if not existing_user:
        await db.add_user(user_id, username, full_name, referred_by=referrer_id, start_bonus=config.START_BONUS)
        if referrer_id:
            bonus = config.REFERRAL_BONUS_PREMIUM if message.from_user.is_premium else config.REFERRAL_BONUS_REGULAR
            await db.add_balance(referrer_id, bonus)
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 Sizning havolangiz orqali yangi do'st qo'shildi!\nSizga +{bonus:,} $PLSR bonus berildi."
                )
            except Exception:
                pass

    is_subscribed = await check_user_subscriptions(user_id)
    if not is_subscribed:
        text = (
            f"⚡ **Pulsar ekotizimiga xush kelibsiz, {full_name}!**\n\n"
            "O'yinni boshlashdan oldin homiylarimizning majburiy Telegram kanallariga a'zo bo'lishingiz shart:\n\n"
            "Kanallarga a'zo bo'lib, pastdagi **'Tekshirish'** tugmasini bosing!"
        )
        keyboard = await get_subscription_keyboard()
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await db.set_user_verified(user_id)
        user = await db.get_user(user_id)
        text = (
            f"✨ **Tabriklaymiz, {full_name}!**\n\n"
            f"🎖 **Darajangiz:** {user['level']}\n"
            f"⚡ **Balansingiz:** {user['balance']:,} $PLSR\n"
            f"💎 **Quasar Kristallari:** {user['quasar_gems']}\n\n"
            "👇 O'yinni boshlash uchun quyidagi tugmani bosing:"
        )
        await message.answer(text, reply_markup=get_main_game_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "verify_subs")
async def process_verify(callback: CallbackQuery):
    user_id = callback.from_user.id
    full_name = callback.from_user.full_name or "O'yinchi"
    is_subscribed = await check_user_subscriptions(user_id)
    if is_subscribed:
        await db.set_user_verified(user_id)
        user = await db.get_user(user_id)
        text = (
            f"🎉 **Barcha obunalar muvaffaqiyatli tekshirildi!**\n\n"
            f"🎖 **Darajangiz:** {user['level']}\n"
            f"⚡ **Balansingiz:** {user['balance']:,} $PLSR\n"
            f"💎 **Quasar Kristallari:** {user['quasar_gems']}\n\n"
            "👇 O'yinni boshlash uchun quyidagi tugmani bosing:"
        )
        await callback.message.edit_text(text, reply_markup=get_main_game_keyboard(), parse_mode="Markdown")
    else:
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)

@dp.callback_query(F.data == "referrals")
async def process_referrals(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    ref_count = await db.get_referral_count(user_id)
    text = (
        "🤝 **Hamkorlik va Referal dasturi**\n\n"
        "Do'stlaringizni taklif qiling va har bir do'st uchun:\n"
        f"• Oddiy foydalanuvchi uchun: **+{config.REFERRAL_BONUS_REGULAR:,} $PLSR**\n"
        f"• Premium foydalanuvchi uchun: **+{config.REFERRAL_BONUS_PREMIUM:,} $PLSR**\n\n"
        f"📊 **Taklif qilgan do'stlaringiz:** {ref_count} ta\n\n"
        f"🔗 **Sizning referal havolangiz:**\n`{ref_link}`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Do'stlarga ulashish",
            url=f"https://t.me/share/url?url={ref_link}&text=Pulsar o'yinida qatnashib, $PLSR tokenlarini yig'ing!")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    text = (
        f"⚡ **Pulsar Bot Menyu**\n\n"
        f"🎖 **Darajangiz:** {user['level']}\n"
        f"⚡ **Balansingiz:** {user['balance']:,} $PLSR\n"
        f"💎 **Quasar Kristallari:** {user['quasar_gems']}\n\n"
        "👇 O'yinni boshlash uchun quyidagi tugmani bosing:"
    )
    await callback.message.edit_text(text, reply_markup=get_main_game_keyboard(), parse_mode="Markdown")

# ============ MAIN ============

async def main():
    await db.init_db()
    await start_web_server()
    asyncio.create_task(keep_alive_self_ping())
    logging.info("Bot polling boshlandi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
