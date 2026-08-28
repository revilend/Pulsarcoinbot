import os
import asyncio
import logging
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

# 1. Render Ping Web Server + Static Files
async def handle_ping(request):
    return web.Response(text="Pulsar Bot is running alive!", status=200)

async def handle_index(request):
    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    if os.path.exists(index_path):
        return web.FileResponse(index_path)
    return web.Response(text="Pulsar Bot is running alive!", status=200)

async def start_web_server():
    app = web.Application()
    
    # Webapp fayllarini xizmat qilish
    webapp_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Static fayllar (css, js, va h.k.)
    app.router.add_static("/css/", webapp_dir, name="css")
    app.router.add_static("/js/", webapp_dir, name="js")
    
    # Asosiy route-lar
    app.router.add_get("/ping", handle_ping)
    app.router.add_get("/", handle_index)
    
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server {port}-portda ishga tushdi.")

# 2. Render Keep-Alive Self Ping Task
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

# 3. Kanallarga a'zolikni tekshirish
async def check_user_subscriptions(user_id: int) -> bool:
    channels = await db.get_all_channels()
    if not channels:
        return True  # Kanal yo'q — tekshirish shart emas
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
        await callback.answer("❌ Hali barcha kanallarga a'zo bo'lmadingiz! Iltimos, tekshirib qayta bosing.", show_alert=True)

@dp.callback_query(F.data == "referrals")
async def process_referrals(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    ref_count = await db.get_referral_count(user_id)

    text = (
        "🤝 **Hamkorlik va Referal dasturi**\n\n"
        "Do'stlaringizni taklif qiling va har bir do'st uchun quyidagi mukofotlarga ega bo'ling:\n"
        f"• Oddiy foydalanuvchi uchun: **+{config.REFERRAL_BONUS_REGULAR:,} $PLSR**\n"
        f"• Premium foydalanuvchi uchun: **+{config.REFERRAL_BONUS_PREMIUM:,} $PLSR**\n\n"
        f"📊 **Taklif qilgan do'stlaringiz:** {ref_count} ta\n\n"
        f"🔗 **Sizning referal havolangiz:**\n`{ref_link}`"
    )
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📲 Do'stlarga ulashish",
                    url=f"https://t.me/share/url?url={ref_link}&text=Pulsar o'yinida qatnashib, $PLSR tokenlarini yig'ing!"
                )
            ],
            [
                InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_to_menu")
            ]
        ]
    )
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

async def main():
    await db.init_db()
    await start_web_server()
    asyncio.create_task(keep_alive_self_ping())
    logging.info("Bot polling boshlandi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
