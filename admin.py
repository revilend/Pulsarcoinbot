import os
import io
import asyncio
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, BufferedInputFile, FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import config
import database as db

admin_router = Router()

class AdminStates(StatesGroup):
    broadcast_message = State()
    create_promo_code = State()
    search_user = State()
    edit_user_balance = State()
    restore_backup_file = State()
    add_channel_id = State()
    add_channel_name = State()
    add_channel_url = State()

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

def get_admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
                InlineKeyboardButton(text="📢 Xabar Tarqatish", callback_data="admin_broadcast")
            ],
            [
                InlineKeyboardButton(text="🔍 O'yinchini Qidirish", callback_data="admin_search_user"),
                InlineKeyboardButton(text="🎁 Yangi Promo-kod", callback_data="admin_create_promo")
            ],
            [
                InlineKeyboardButton(text="📢 Kanallar", callback_data="admin_channels"),
                InlineKeyboardButton(text="📥 Baza Backup", callback_data="admin_backup_download")
            ],
            [
                InlineKeyboardButton(text="📤 Bazani Tiklash", callback_data="admin_restore_prompt")
            ],
            [
                InlineKeyboardButton(text="◀️ Panelni Yopish", callback_data="admin_close")
            ]
        ]
    )

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda ushbu boʻlimga kirish huquqi yoʻq!")
        return

    text = (
        "🛠 **Pulsar Bot — Boshqaruv Admin Paneli**\n\n"
        "Kerakli boʻlimni tanlang:"
    )
    await message.answer(text, reply_markup=get_admin_main_kb(), parse_mode="Markdown")

# 1. Statistika
@admin_router.callback_query(F.data == "admin_stats")
async def process_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return

    total_users = await db.get_total_users_count()
    total_plsr, total_gems = await db.get_total_economy()

    text = (
        "📊 **Bot Statistikasi:**\n\n"
        f"👥 **Jami o'yinchilar:** {total_users:,} ta\n"
        f"⚡ **Jami $PLSR aylanmasi:** {total_plsr:,} $PLSR\n"
        f"💎 **Jami Quasar kristallari:** {total_gems:,} dona\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_stats")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# 2. Baza Backup Yuklab Olish (Download Full DB & JSON)
@admin_router.callback_query(F.data == "admin_backup_download")
async def process_admin_backup_download(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id): return

    await callback.answer("⏳ Backup tayyorlanmoqda...")
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # 1. SQLite .db faylini yuborish
    if os.path.exists(db.DB_NAME):
        db_file = FSInputFile(db.DB_NAME, filename=f"pulsar_backup_{now_str}.db")
        await bot.send_document(
            chat_id=callback.from_user.id,
            document=db_file,
            caption="📦 **To'liq SQLite ma'lumotlar bazasi fayli (.db)**"
        )

    # 2. O'qish oson bo'lgan JSON backup yuborish
    json_data = await db.export_all_data_json()
    json_bytes = json_data.encode("utf-8")
    json_file = BufferedInputFile(json_bytes, filename=f"pulsar_users_{now_str}.json")
    
    await bot.send_document(
        chat_id=callback.from_user.id,
        document=json_file,
        caption="📄 **Foydalanuvchilar va barcha hisoblar JSON backup fayli**"
    )

    await callback.message.answer(
        "✅ **Barcha ma'lumotlar muvaffaqiyatli yuborildi!**\nUshbu fayllarni saqlab qo'yishingiz mumkin.",
        reply_markup=get_admin_main_kb()
    )

# 3. Bazani Qayta Yuklash / Tiklash (Restore)
@admin_router.callback_query(F.data == "admin_restore_prompt")
async def process_admin_restore_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return

    await state.set_state(AdminStates.restore_backup_file)
    await callback.message.edit_text(
        "📤 **Bazani qayta yuklash (Restore):**\n\n"
        "Iltimos, avval yuklab olingan `.json` yoki `.db` backup faylini botga yuboring (fayl/document sifatida).\n\n"
        "Bekor qilish uchun /cancel deb yozing.",
        parse_mode="Markdown"
    )

@admin_router.message(AdminStates.restore_backup_file, F.document)
async def process_restore_document(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    await state.clear()

    if doc.file_name.endswith(".json"):
        # JSON faylni yuklab o'qish
        file_obj = await bot.get_file(doc.file_id)
        file_bytes = await bot.download_file(file_obj.file_path)
        content = file_bytes.read().decode("utf-8")
        
        try:
            users_count, promo_count = await db.import_data_from_json(content)
            await message.answer(
                f"✅ **JSON ma'lumotlari muvaffaqiyatli tiklandi!**\n\n"
                f"👥 Tiklangan o'yinchilar: {users_count} ta\n"
                f"🎁 Tiklangan promo-kodlar: {promo_count} ta",
                reply_markup=get_admin_main_kb(),
                parse_mode="Markdown"
            )
        except Exception as e:
            await message.answer(f"❌ Xatolik yuz berdi: {e}", reply_markup=get_admin_main_kb())

    elif doc.file_name.endswith(".db"):
        # SQLite .db faylini almashtirish
        file_obj = await bot.get_file(doc.file_id)
        await bot.download_file(file_obj.file_path, destination=db.DB_NAME)
        await message.answer(
            "✅ **SQLite bazasi to'liq almashtirildi va tiklandi!**",
            reply_markup=get_admin_main_kb()
        )
    else:
        await message.answer("⚠️ Faqat `.json` yoki `.db` formatidagi backup fayllar qabul qilinadi!", reply_markup=get_admin_main_kb())

# 4. O'yinchini Qidirish va Ma'lumotlarini ko'rish
@admin_router.callback_query(F.data == "admin_search_user")
async def process_admin_search_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return

    await state.set_state(AdminStates.search_user)
    await callback.message.edit_text(
        "🔍 O'yinchining **Telegram ID** raqamini yoki **@username** ini yozib yuboring:\n\n"
        "Bekor qilish uchun /cancel deb yozing.",
        parse_mode="Markdown"
    )

@admin_router.message(AdminStates.search_user)
async def execute_user_search(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Qidiruv bekor qilindi.", reply_markup=get_admin_main_kb())
        return

    query = message.text.strip()
    user = None
    if query.isdigit():
        user = await db.get_user(int(query))
    else:
        user = await db.get_user_by_username(query)

    if not user:
        await message.answer("❌ O'yinchi topilmadi! Qaytadan kiriting yoki /cancel deb yozing.")
        return

    await state.clear()
    ref_count = await db.get_referral_count(user["user_id"])
    text = (
        f"👤 **O'yinchi Ma'lumotlari:**\n\n"
        f"🆔 ID: `{user['user_id']}`\n"
        f"🏷 Ism: {user['full_name']}\n"
        f"🌐 Username: @{user['username'] if user['username'] else 'Yoʻq'}\n"
        f"⚡ Balans: **{user['balance']:,} $PLSR**\n"
        f"💎 Quasar: **{user['quasar_gems']}**\n"
        f"🎖 Daraja: {user['level']} (XP: {user['xp']})\n"
        f"👥 Taklif qilgan do'stlari: {ref_count} ta\n"
        f"📅 Qo'shilgan vaqti: {user['created_at'][:19]}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ 10,000 $PLSR", callback_data=f"give_plsr_{user['user_id']}_10000"),
            InlineKeyboardButton(text="➕ 50,000 $PLSR", callback_data=f"give_plsr_{user['user_id']}_50000")
        ],
        [
            InlineKeyboardButton(text="💎 ➕5 Quasar", callback_data=f"give_gems_{user['user_id']}_5"),
            InlineKeyboardButton(text="💎 ➕20 Quasar", callback_data=f"give_gems_{user['user_id']}_20")
        ],
        [InlineKeyboardButton(text="◀️ Bosh Menyu", callback_data="admin_back")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# Balans qo'shish callbacklari
@admin_router.callback_query(F.data.startswith("give_plsr_"))
async def process_give_plsr(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    _, _, uid, amount = callback.data.split("_")
    await db.add_balance(int(uid), int(amount))
    await callback.answer(f"✅ +{int(amount):,} $PLSR muvaffaqiyatli qo'shildi!", show_alert=True)

@admin_router.callback_query(F.data.startswith("give_gems_"))
async def process_give_gems(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    _, _, uid, amount = callback.data.split("_")
    await db.add_gems(int(uid), int(amount))
    await callback.answer(f"✅ +{amount} Quasar kristali qo'shildi!", show_alert=True)

# 5. Xabar Tarqatish (Broadcast)
@admin_router.callback_query(F.data == "admin_broadcast")
async def process_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return

    await state.set_state(AdminStates.broadcast_message)
    await callback.message.edit_text(
        "✍️ Barcha oʻyinchilarga yubormoqchi boʻlgan xabaringizni yuboring (matn, rasm yoki video):\n\n"
        "Bekor qilish uchun /cancel yozing."
    )

@admin_router.message(AdminStates.broadcast_message)
async def execute_broadcast(message: Message, state: FSMContext, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_kb())
        return

    await state.clear()
    user_ids = await db.get_all_user_ids()
    status_msg = await message.answer(f"⏳ Xabar tarqatilmoqda... Jami: {len(user_ids)} ta foydalanuvchi.")

    success_count = 0
    fail_count = 0

    for uid in user_ids:
        try:
            await message.copy_to(chat_id=uid)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ **Xabar tarqatish yakunlandi!**\n\n"
        f"🟢 Yuborildi: {success_count} ta\n"
        f"🔴 Bloklaganlar: {fail_count} ta",
        reply_markup=get_admin_main_kb(),
        parse_mode="Markdown"
    )

# 6. Promo-kod Yaratish
@admin_router.callback_query(F.data == "admin_create_promo")
async def process_admin_promo(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return

    await state.set_state(AdminStates.create_promo_code)
    await callback.message.edit_text(
        "🎁 Yangi promo-kod formatini kiriting:\n\n"
        "`KOD MUKOFOT_PLSR SONI`\n\n"
        "Masalan:\n`PULSAR2026 50000 100`\n\n"
        "Bekor qilish uchun /cancel yozing.",
        parse_mode="Markdown"
    )

@admin_router.message(AdminStates.create_promo_code)
async def save_promo_code(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_kb())
        return

    try:
        parts = message.text.split()
        code = parts[0]
        reward = int(parts[1])
        max_uses = int(parts[2])

        await db.create_promo_code(code, reward, max_uses)
        await state.clear()
        await message.answer(
            f"✅ **Promo-kod yaratildi!**\n\n"
            f"🔑 Kod: `{code.upper()}`\n"
            f"⚡ Mukofot: {reward:,} $PLSR\n"
            f"👥 Soni: {max_uses} ta foydalanuvchi",
            reply_markup=get_admin_main_kb(),
            parse_mode="Markdown"
        )
    except Exception:
        await message.answer("⚠️ Notoʻgʻri format! Qaytadan kiriting yoki /cancel bosing.")

@admin_router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await callback.message.edit_text("🛠 **Pulsar Bot — Admin Paneli**", reply_markup=get_admin_main_kb(), parse_mode="Markdown")

@admin_router.callback_query(F.data == "admin_close")
async def admin_close(callback: CallbackQuery):
    await callback.message.delete()

# ============ KANALLARNI BOSHQARISH ============

@admin_router.callback_query(F.data == "admin_channels")
async def process_admin_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return

    channels = await db.get_all_channels()
    channel_count = len(channels)

    text = (
        "📢 **Majburiy Kanallar Boshqaruvi**\n\n"
        f"Jami kanallar: **{channel_count}** ta\n\n"
        "Quyidagi kanallar foydalanuvchilardan majburiy obuna talab qiladi:\n"
    )

    if channels:
        for i, ch in enumerate(channels, start=1):
            text += f"\n{i}. **{ch['name']}**\n   🆔 `{ch['channel_id']}`\n   🔗 {ch['url']}"
    else:
        text += "\n\n⚠️ Hozircha kanallar yo'q. Foydalanuvchilardan obuna talab qilinmaydi."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Kanal Qo'shish", callback_data="admin_add_channel"),
            InlineKeyboardButton(text="➖ Kanal O'chirish", callback_data="admin_remove_channel_list")
        ],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# Kanal qo'shish — 1-qadam: channel_id
@admin_router.callback_query(F.data == "admin_add_channel")
async def process_add_channel_step1(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return

    await state.set_state(AdminStates.add_channel_id)
    await callback.message.edit_text(
        "➕ **Yangi Kanal Qo'shish — 1/3**\n\n"
        "Kanalning **username** (masalan: `@pulsar_news`) yoki **channel ID** (masalan: `-1001234567890`) ni yuboring:\n\n"
        "💡 ID ni olish uchun: @userinfobot ga kanal xabarini forward qiling.\n\n"
        "Bekor qilish uchun /cancel yozing.",
        parse_mode="Markdown"
    )

@admin_router.message(AdminStates.add_channel_id)
async def process_add_channel_step2(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_kb())
        return

    channel_id = message.text.strip()
    await state.update_data(channel_id=channel_id)
    await state.set_state(AdminStates.add_channel_name)
    await message.answer(
        f"➕ **Yangi Kanal Qo'shish — 2/3**\n\n"
        f"Kanal ID: `{channel_id}`\n\n"
        "Endi kanalning **ko'rinish nomini** yuboring (masalan: `Pulsar Rasmiy Kanal`)\n\n"
        "Bekor qilish uchun /cancel yozing.",
        parse_mode="Markdown"
    )

@admin_router.message(AdminStates.add_channel_name)
async def process_add_channel_step3(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_kb())
        return

    channel_name = message.text.strip()
    await state.update_data(channel_name=channel_name)
    await state.set_state(AdminStates.add_channel_url)
    await message.answer(
        f"➕ **Yangi Kanal Qo'shish — 3/3**\n\n"
        f"Kanal: **{channel_name}**\n\n"
        "Endi kanalning **havolasini** (URL) yuboring:\n"
        "Masalan: `https://t.me/pulsar_news`\n\n"
        "Bekor qilish uchun /cancel yozing.",
        parse_mode="Markdown"
    )

@admin_router.message(AdminStates.add_channel_url)
async def process_add_channel_save(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_main_kb())
        return

    channel_url = message.text.strip()
    data = await state.get_data()
    channel_id = data.get("channel_id")
    channel_name = data.get("channel_name")

    await state.clear()

    if not channel_url.startswith("http"):
        await message.answer(
            "⚠️ Noto'g'ri URL formati! URL `https://` bilan boshlanishi kerak.\n"
            "Qaytadan boshlash uchun /admin ni bosing.",
            reply_markup=get_admin_main_kb()
        )
        return

    await db.add_channel(channel_id, channel_name, channel_url)
    await message.answer(
        f"✅ **Kanal muvaffaqiyatli qo'shildi!**\n\n"
        f"🆔 ID: `{channel_id}`\n"
        f"📛 Nom: **{channel_name}**\n"
        f"🔗 Havola: {channel_url}\n\n"
        "Endi foydalanuvchilar ushbu kanalga a'zo bo'lishi shart.",
        reply_markup=get_admin_main_kb(),
        parse_mode="Markdown"
    )

# Kanal o'chirish — ro'yxat
@admin_router.callback_query(F.data == "admin_remove_channel_list")
async def process_remove_channel_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return

    channels = await db.get_all_channels()
    if not channels:
        await callback.message.edit_text(
            "⚠️ O'chiriladigan kanallar yo'q.\n\n"
            "Qo'shish uchun 'Kanallar' bo'limiga qayting.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_channels")]
            ])
        )
        return

    text = "➖ **Kanalni O'chirish**\n\nO'chirmoqchi bo'lgan kanalni tanlang:\n\n"
    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {ch['name']} ({ch['channel_id']})",
            callback_data=f"admin_rm_ch_{ch['channel_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_channels")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

# Kanal o'chirish — tasdiqlash
@admin_router.callback_query(F.data.startswith("admin_rm_ch_"))
async def process_remove_channel_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return

    channel_id = callback.data.replace("admin_rm_ch_", "")
    channel = await db.get_channel(channel_id)

    if not channel:
        await callback.answer("❌ Kanal topilmadi!", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"admin_rm_ch_yes_{channel_id}"),
            InlineKeyboardButton(text="❌ Yo'q, bekor", callback_data="admin_channels")
        ]
    ])
    await callback.message.edit_text(
        f"⚠️ **O'chirishni tasdiqlang**\n\n"
        f"Kanal: **{channel['name']}**\n"
        f"ID: `{channel['channel_id']}\n"
        f"Havola: {channel['url']}`\n\n"
        "Ushbu kanal obuna talablaridan o'chiriladi.\n"
        "Davom etasizmi?",
        reply_markup=kb, parse_mode="Markdown"
    )

# Kanal o'chirish — amalga oshirish
@admin_router.callback_query(F.data.startswith("admin_rm_ch_yes_"))
async def process_remove_channel_execute(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return

    channel_id = callback.data.replace("admin_rm_ch_yes_", "")
    channel = await db.get_channel(channel_id)
    channel_name = channel['name'] if channel else channel_id

    await db.remove_channel(channel_id)
    await callback.answer(f"✅ '{channel_name}' kanali o'chirildi!", show_alert=True)

    # Kanallar ro'yxatiga qaytish
    channels = await db.get_all_channels()
    channel_count = len(channels)

    text = (
        "📢 **Majburiy Kanallar Boshqaruvi**\n\n"
        f"Jami kanallar: **{channel_count}** ta\n\n"
        "Quyidagi kanallar foydalanuvchilardan majburiy obuna talab qiladi:\n"
    )

    if channels:
        for i, ch in enumerate(channels, start=1):
            text += f"\n{i}. **{ch['name']}**\n   🆔 `{ch['channel_id']}`\n   🔗 {ch['url']}"
    else:
        text += "\n\n⚠️ Hozircha kanallar yo'q. Foydalanuvchilardan obuna talab qilinmaydi."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Kanal Qo'shish", callback_data="admin_add_channel"),
            InlineKeyboardButton(text="➖ Kanal O'chirish", callback_data="admin_remove_channel_list")
        ],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
