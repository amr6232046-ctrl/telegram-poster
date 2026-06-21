import os
import logging
from datetime import datetime, timezone, timedelta
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
TZ = timezone(timedelta(hours=5))

USERS_FILE = "users.json"
SCHEDULES_FILE = "schedules.json"

def now_uz():
    return datetime.now(TZ)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_schedules():
    if os.path.exists(SCHEDULES_FILE):
        with open(SCHEDULES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_schedules(data):
    with open(SCHEDULES_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user(user_id):
    users = load_users()
    return users.get(str(user_id))

def set_user(user_id, data):
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

def is_blocked(user_id):
    user = get_user(user_id)
    return user and user.get("blocked", False)

def get_user_schedules(user_id):
    schedules = load_schedules()
    return schedules.get(str(user_id), [])

def save_user_schedules(user_id, items):
    schedules = load_schedules()
    schedules[str(user_id)] = items
    save_schedules(schedules)

scheduler = AsyncIOScheduler(timezone=TZ)

TYPE_ICONS = {
    "photo": "🖼", "video": "🎥", "audio": "🎵",
    "document": "📄", "animation": "🎞", "voice": "🎤", "video_note": "⭕"
}
TYPE_NAMES = {
    "photo": "Rasm", "video": "Video", "audio": "Musiqa",
    "document": "Fayl", "animation": "GIF", "voice": "Ovozli", "video_note": "Video doira"
}

# ─── START ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_blocked(user_id):
        await update.message.reply_text("❌ Siz botdan foydalana olmaysiz.")
        return

    user = get_user(user_id)

    # Yangi foydalanuvchi — adminга xabar
    if not user:
        try:
            tg_user = update.effective_user
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🆕 *Yangi foydalanuvchi!*\n\n"
                     f"👤 Ism: {tg_user.full_name}\n"
                     f"🆔 ID: `{user_id}`\n"
                     f"👤 Username: @{tg_user.username or 'yoq'}\n\n"
                     f"Bloklash: `/block {user_id}`",
                parse_mode="Markdown"
            )
        except:
            pass

    if user and user.get("channel") and not user.get("blocked"):
        now = now_uz()
        await update.message.reply_text(
            f"👋 Xush kelibsiz!\n\n"
            f"📢 Sizning kanalingiz: `{user['channel']}`\n"
            f"🕐 Toshkent vaqti: *{now.strftime('%H:%M')}*\n\n"
            f"Fayl yuboring — men vaqt so'rayman!\n\n"
            f"/mychannel — kanalni o'zgartirish\n"
            f"/list — rejalashtirilgan postlar\n"
            f"/cancel — oxirgi postni bekor qilish\n"
            f"/status — holat",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "👋 *Kanal Auto-Post Botiga xush kelibsiz!*\n\n"
            "Bu bot kanalingizga belgilangan vaqtda post yuboradi.\n\n"
            "📢 Kanalingiz username ini yuboring:\n"
            "Masalan: `@mening_kanalim`\n\n"
            "⚠️ Botni kanalingizga *admin* qilib qo'shishni unutmang!",
            parse_mode="Markdown"
        )
        context.user_data["waiting_channel"] = True

async def mychannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id):
        return
    user = get_user(user_id)
    channel = user.get("channel", "Belgilanmagan") if user else "Belgilanmagan"
    keyboard = [[InlineKeyboardButton("✏️ Kanalni o'zgartirish", callback_data="change_channel")]]
    await update.message.reply_text(
        f"📢 Sizning kanalingiz: `{channel}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── MATN QABUL QILISH ───────────────────────────────────────────────────────

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id):
        return

    text = update.message.text.strip()

    if context.user_data.get("waiting_channel"):
        if not text.startswith("@"):
            await update.message.reply_text(
                "❌ @ bilan boshlang. Masalan: `@mening_kanalim`",
                parse_mode="Markdown"
            )
            return

        existing = get_user(user_id) or {}
        existing.update({
            "channel": text,
            "name": update.effective_user.full_name,
            "username": update.effective_user.username or "",
            "joined": now_uz().isoformat()
        })
        set_user(user_id, existing)
        context.user_data.pop("waiting_channel", None)

        await update.message.reply_text(
            f"✅ *Kanal saqlandi:* `{text}`\n\n"
            f"Endi fayl yuboring — men vaqt so'rayman!\n\n"
            f"⚠️ Botni `{text}` kanaliga *admin* qilib qo'shing!",
            parse_mode="Markdown"
        )
        return

    if context.user_data.get("setting_time_for") is not None or context.user_data.get("waiting_time"):
        await process_time(update, context, text)

async def process_time(update, context, text):
    user_id = update.effective_user.id

    try:
        hour, minute = map(int, text.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Format: `09:00`", parse_mode="Markdown")
        return

    user = get_user(user_id)
    if not user or not user.get("channel"):
        await update.message.reply_text("❌ Avval /start orqali kanal belgilang!")
        return

    channel = user["channel"]
    queue = context.user_data.get("queue", [])
    idx = context.user_data.get("setting_time_for", len(queue) - 1)

    if not queue or idx >= len(queue):
        await update.message.reply_text("❌ Fayl topilmadi, avval fayl yuboring!")
        return

    item = queue[idx]
    now = now_uz()
    send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    tomorrow = False
    if send_time <= now:
        send_time += timedelta(days=1)
        tomorrow = True

    user_schedules = get_user_schedules(user_id)
    schedule_id = f"u{user_id}_{hour:02d}{minute:02d}_{len(user_schedules)}"

    new_schedule = {
        "id": schedule_id,
        "file_id": item["file_id"],
        "file_type": item["file_type"],
        "caption": item["caption"],
        "channel": channel,
        "hour": hour,
        "minute": minute,
        "send_time": send_time.isoformat()
    }

    user_schedules.append(new_schedule)
    save_user_schedules(user_id, user_schedules)
    add_once_job(context.application, new_schedule, send_time, user_id)

    queue.pop(idx)
    context.user_data["queue"] = queue
    context.user_data.pop("setting_time_for", None)
    context.user_data.pop("waiting_time", None)

    icon = TYPE_ICONS.get(item["file_type"], "📎")
    when = "ertaga" if tomorrow else "bugun"
    remaining = len(queue)
    extra = f"\n\n📋 Navbatda yana *{remaining}* ta fayl — /queue" if remaining > 0 else ""

    await update.message.reply_text(
        f"✅ {icon} *{when} {hour:02d}:{minute:02d}* da yuboriladi!\n"
        f"📢 `{channel}`{extra}",
        parse_mode="Markdown"
    )

# ─── FAYL QABUL QILISH ───────────────────────────────────────────────────────

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id):
        return

    user = get_user(user_id)
    if not user or not user.get("channel"):
        await update.message.reply_text("❌ Avval /start bosing va kanal belgilang!")
        return

    msg = update.message
    if msg.photo:
        file_id = msg.photo[-1].file_id; file_type = "photo"
    elif msg.video:
        file_id = msg.video.file_id; file_type = "video"
    elif msg.audio:
        file_id = msg.audio.file_id; file_type = "audio"
    elif msg.document:
        file_id = msg.document.file_id; file_type = "document"
    elif msg.animation:
        file_id = msg.animation.file_id; file_type = "animation"
    elif msg.voice:
        file_id = msg.voice.file_id; file_type = "voice"
    elif msg.video_note:
        file_id = msg.video_note.file_id; file_type = "video_note"
    else:
        return

    caption = msg.caption or ""
    if "queue" not in context.user_data:
        context.user_data["queue"] = []
    context.user_data["queue"].append({"file_id": file_id, "file_type": file_type, "caption": caption})

    queue = context.user_data["queue"]
    count = len(queue)
    icon = TYPE_ICONS.get(file_type, "📎")
    name = TYPE_NAMES.get(file_type, "Fayl")
    now = now_uz()

    keyboard = [[
        InlineKeyboardButton("⏰ Vaqt belgilash", callback_data=f"set_time_{count-1}"),
        InlineKeyboardButton("➕ Yana fayl", callback_data="add_more")
    ]]
    await msg.reply_text(
        f"{icon} *{name}* qabul qilindi! ({count}-fayl)\n"
        f"🕐 Hozir: *{now.strftime('%H:%M')}* | 📢 `{user['channel']}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── TUGMALAR ────────────────────────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "change_channel":
        context.user_data["waiting_channel"] = True
        await query.edit_message_text("📢 Yangi kanal username ini yuboring:\nMasalan: `@kanal`", parse_mode="Markdown")

    elif query.data == "add_more":
        queue = context.user_data.get("queue", [])
        await query.edit_message_text(f"✅ Navbatda *{len(queue)}* ta fayl.\nKeyingi faylni yuboring yoki /queue", parse_mode="Markdown")

    elif query.data.startswith("set_time_"):
        idx = int(query.data.split("_")[-1])
        context.user_data["setting_time_for"] = idx
        now = now_uz()
        queue = context.user_data.get("queue", [])
        if idx < len(queue):
            icon = TYPE_ICONS.get(queue[idx]["file_type"], "📎")
            await query.edit_message_text(
                f"{icon} *{idx+1}-fayl* uchun vaqt:\n"
                f"🕐 Hozir: *{now.strftime('%H:%M')}*\n"
                f"Masalan: `09:00` _(o'tgan bo'lsa ertaga)_",
                parse_mode="Markdown"
            )

# ─── BUYRUQLAR ───────────────────────────────────────────────────────────────

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id): return
    schedules = get_user_schedules(user_id)
    if not schedules:
        await update.message.reply_text("📭 Rejalashtirilgan post yo'q.")
        return
    text = f"📅 *Rejalashtirilgan ({len(schedules)} ta):*\n\n"
    for i, s in enumerate(schedules, 1):
        icon = TYPE_ICONS.get(s["file_type"], "📎")
        t = datetime.fromisoformat(s["send_time"])
        text += f"{i}. {icon} *{t.strftime('%d.%m %H:%M')}*\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id): return
    queue = context.user_data.get("queue", [])
    if not queue:
        await update.message.reply_text("📭 Navbatda fayl yo'q. Fayl yuboring!")
        return
    text = f"📋 *Navbat ({len(queue)} ta):*\n\n"
    keyboard = []
    for i, item in enumerate(queue):
        icon = TYPE_ICONS.get(item["file_type"], "📎")
        text += f"{i+1}. {icon} {TYPE_NAMES.get(item['file_type'], 'Fayl')}\n"
        keyboard.append([InlineKeyboardButton(f"⏰ {i+1}-faylga vaqt", callback_data=f"set_time_{i}")])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id): return
    schedules = get_user_schedules(user_id)
    if not schedules:
        await update.message.reply_text("📭 Bekor qilish uchun post yo'q.")
        return
    last = schedules.pop()
    save_user_schedules(user_id, schedules)
    if scheduler.get_job(last["id"]):
        scheduler.remove_job(last["id"])
    t = datetime.fromisoformat(last["send_time"])
    await update.message.reply_text(f"✅ Bekor qilindi: *{t.strftime('%d.%m %H:%M')}*", parse_mode="Markdown")

async def cancelall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id): return
    schedules = get_user_schedules(user_id)
    for s in schedules:
        if scheduler.get_job(s["id"]):
            scheduler.remove_job(s["id"])
    save_user_schedules(user_id, [])
    context.user_data["queue"] = []
    await update.message.reply_text(f"✅ *{len(schedules)}* ta post bekor qilindi!", parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_blocked(user_id): return
    user = get_user(user_id)
    channel = user.get("channel", "Belgilanmagan") if user else "Belgilanmagan"
    schedules = get_user_schedules(user_id)
    queue = context.user_data.get("queue", [])
    now = now_uz()
    await update.message.reply_text(
        f"🤖 *Bot holati:* Ishlayapti ✅\n\n"
        f"🕐 Toshkent vaqti: *{now.strftime('%H:%M')}*\n"
        f"📢 Sizning kanalingiz: `{channel}`\n"
        f"📅 Rejalashtirilgan: *{len(schedules)}* ta\n"
        f"📋 Navbatda: *{len(queue)}* ta",
        parse_mode="Markdown"
    )

# ─── ADMIN BUYRUQLARI ────────────────────────────────────────────────────────

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = load_users()
    if not users:
        await update.message.reply_text("📭 Foydalanuvchi yo'q.")
        return
    text = f"👥 *Foydalanuvchilar ({len(users)} ta):*\n\n"
    for uid, u in list(users.items())[:30]:
        blocked = " 🚫" if u.get("blocked") else ""
        text += f"• {u.get('name','?')}{blocked} — `{u.get('channel','?')}` | ID: `{uid}`\n"
    text += "\nBloklash: `/block ID`\nRuxsat: `/unblock ID`"
    await update.message.reply_text(text, parse_mode="Markdown")

async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("❌ ID kiriting: `/block 123456789`", parse_mode="Markdown")
        return
    target_id = context.args[0]
    user = get_user(target_id)
    if not user:
        await update.message.reply_text("❌ Foydalanuvchi topilmadi!")
        return
    user["blocked"] = True
    set_user(target_id, user)
    try:
        await context.bot.send_message(chat_id=int(target_id), text="❌ Siz botdan bloklandingiz.")
    except:
        pass
    await update.message.reply_text(f"✅ `{target_id}` bloklandi!", parse_mode="Markdown")

async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("❌ ID kiriting: `/unblock 123456789`", parse_mode="Markdown")
        return
    target_id = context.args[0]
    user = get_user(target_id)
    if not user:
        await update.message.reply_text("❌ Foydalanuvchi topilmadi!")
        return
    user["blocked"] = False
    set_user(target_id, user)
    try:
        await context.bot.send_message(chat_id=int(target_id), text="✅ Blokiniz olib tashlandi! /start bosing.")
    except:
        pass
    await update.message.reply_text(f"✅ `{target_id}` blokdan chiqarildi!", parse_mode="Markdown")

# ─── JOB ─────────────────────────────────────────────────────────────────────

def add_once_job(app, schedule, send_time, user_id):
    async def send_and_delete():
        try:
            bot = app.bot
            ftype = schedule["file_type"]
            fid = schedule["file_id"]
            cap = schedule.get("caption", "") or ""
            ch = schedule["channel"]

            if ftype == "photo":
                await bot.send_photo(chat_id=ch, photo=fid, caption=cap)
            elif ftype == "video":
                await bot.send_video(chat_id=ch, video=fid, caption=cap)
            elif ftype == "audio":
                await bot.send_audio(chat_id=ch, audio=fid, caption=cap)
            elif ftype == "document":
                await bot.send_document(chat_id=ch, document=fid, caption=cap)
            elif ftype == "animation":
                await bot.send_animation(chat_id=ch, animation=fid, caption=cap)
            elif ftype == "voice":
                await bot.send_voice(chat_id=ch, voice=fid, caption=cap)
            elif ftype == "video_note":
                await bot.send_video_note(chat_id=ch, video_note=fid)

            schedules = get_user_schedules(user_id)
            schedules = [s for s in schedules if s["id"] != schedule["id"]]
            save_user_schedules(user_id, schedules)

            t = datetime.fromisoformat(schedule["send_time"]).strftime('%H:%M')
            await bot.send_message(chat_id=user_id, text=f"✅ Post yuborildi! ⏰ {t} | 📢 {ch}")

        except Exception as e:
            logger.error(f"Xato: {e}")
            try:
                await app.bot.send_message(chat_id=user_id, text=f"❌ Xato: {e}\n\nBot kanalga admin qilinganmi?")
            except:
                pass

    scheduler.add_job(send_and_delete, DateTrigger(run_date=send_time), id=schedule["id"], replace_existing=True)

# ─── MAIN ────────────────────────────────────────────────────────────────────

async def post_init(application):
    now = now_uz()
    schedules_data = load_schedules()
    total = 0
    for user_id, items in schedules_data.items():
        valid = []
        for s in items:
            send_time = datetime.fromisoformat(s["send_time"])
            if send_time > now:
                add_once_job(application, s, send_time, int(user_id))
                valid.append(s)
        schedules_data[user_id] = valid
        total += len(valid)
    save_schedules(schedules_data)
    scheduler.start()
    logger.info(f"Bot ishga tushdi. {total} ta post kutmoqda.")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN yo'q!")
    if not ADMIN_ID:
        raise ValueError("ADMIN_ID yo'q!")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mychannel", mychannel_command))
    app.add_handler(CommandHandler("queue", queue_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("cancelall", cancelall_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CommandHandler("block", block_command))
    app.add_handler(CommandHandler("unblock", unblock_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.AUDIO |
        filters.Document.ALL | filters.ANIMATION |
        filters.VOICE | filters.VIDEO_NOTE,
        receive_file
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text))

    logger.info("Bot polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
