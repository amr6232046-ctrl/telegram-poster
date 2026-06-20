import os
import logging
import asyncio
from datetime import datetime, time
from typing import Dict, List
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Tashkent")

STORAGE_FILE = "scheduled_files.json"

def load_data():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r") as f:
            return json.load(f)
    return {"schedules": []}

def save_data(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)

scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return

    text = (
        "👋 *Kanal Auto-Post Boti*\n\n"
        "📌 *Qanday ishlatiladi:*\n\n"
        "1️⃣ Menga rasm/video/fayl yuboring\n"
        "2️⃣ Keyin vaqt belgilang: `/schedule 09:00`\n"
        "3️⃣ Bot har kuni o'sha vaqtda kanalga yuboradi\n\n"
        "📋 *Buyruqlar:*\n"
        "/schedule HH:MM — vaqt belgilash\n"
        "/list — barcha rejalashtirilgan postlar\n"
        "/delete — postni o'chirish\n"
        "/status — bot holati\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = update.message

    if msg.photo:
        file_id = msg.photo[-1].file_id
        file_type = "photo"
    elif msg.video:
        file_id = msg.video.file_id
        file_type = "video"
    elif msg.audio:
        file_id = msg.audio.file_id
        file_type = "audio"
    elif msg.document:
        file_id = msg.document.file_id
        file_type = "document"
    elif msg.animation:
        file_id = msg.animation.file_id
        file_type = "animation"
    elif msg.voice:
        file_id = msg.voice.file_id
        file_type = "voice"
    elif msg.video_note:
        file_id = msg.video_note.file_id
        file_type = "video_note"
    else:
        return

    caption = msg.caption or ""

    context.user_data["pending_file"] = {
        "file_id": file_id,
        "file_type": file_type,
        "caption": caption
    }

    type_names = {
        "photo": "🖼 Rasm",
        "video": "🎥 Video",
        "audio": "🎵 Musiqa",
        "document": "📄 Fayl",
        "animation": "🎞 GIF",
        "voice": "🎤 Ovozli xabar",
        "video_note": "⭕ Video doira"
    }

    await msg.reply_text(
        f"✅ *{type_names.get(file_type, 'Fayl')}* qabul qilindi!\n\n"
        f"⏰ Endi vaqt belgilang:\n`/schedule 09:00`\n\n"
        f"_(O'zbekiston vaqti bo'yicha)_",
        parse_mode="Markdown"
    )

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Vaqt kiriting!\nMisol: `/schedule 09:00`",
            parse_mode="Markdown"
        )
        return

    time_str = context.args[0]

    try:
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Noto'g'ri vaqt formati!\nTo'g'ri format: `09:00` yoki `21:30`",
            parse_mode="Markdown"
        )
        return

    pending = context.user_data.get("pending_file")
    if not pending:
        await update.message.reply_text(
            "❌ Avval menga fayl yuboring, keyin vaqt belgilang!",
        )
        return

    data = load_data()

    schedule_id = f"post_{hour:02d}{minute:02d}_{len(data['schedules'])}"

    new_schedule = {
        "id": schedule_id,
        "file_id": pending["file_id"],
        "file_type": pending["file_type"],
        "caption": pending["caption"],
        "hour": hour,
        "minute": minute,
        "created_at": datetime.now().isoformat()
    }

    data["schedules"].append(new_schedule)
    save_data(data)

    add_job_to_scheduler(context.application, new_schedule)

    context.user_data.pop("pending_file", None)

    await update.message.reply_text(
        f"✅ *Muvaffaqiyatli rejalashtirildi!*\n\n"
        f"⏰ Vaqt: *{hour:02d}:{minute:02d}* (O'zbekiston)\n"
        f"📢 Kanal: `{CHANNEL_ID}`\n"
        f"🔄 Har kuni avtomatik yuboriladi",
        parse_mode="Markdown"
    )

def add_job_to_scheduler(app, schedule):
    async def send_post():
        try:
            bot = app.bot
            ftype = schedule["file_type"]
            fid = schedule["file_id"]
            cap = schedule.get("caption", "") or ""

            if ftype == "photo":
                await bot.send_photo(chat_id=CHANNEL_ID, photo=fid, caption=cap)
            elif ftype == "video":
                await bot.send_video(chat_id=CHANNEL_ID, video=fid, caption=cap)
            elif ftype == "audio":
                await bot.send_audio(chat_id=CHANNEL_ID, audio=fid, caption=cap)
            elif ftype == "document":
                await bot.send_document(chat_id=CHANNEL_ID, document=fid, caption=cap)
            elif ftype == "animation":
                await bot.send_animation(chat_id=CHANNEL_ID, animation=fid, caption=cap)
            elif ftype == "voice":
                await bot.send_voice(chat_id=CHANNEL_ID, voice=fid, caption=cap)
            elif ftype == "video_note":
                await bot.send_video_note(chat_id=CHANNEL_ID, video_note=fid)

            logger.info(f"Post yuborildi: {schedule['id']} -> {CHANNEL_ID}")
        except Exception as e:
            logger.error(f"Post yuborishda xato: {e}")

    scheduler.add_job(
        send_post,
        CronTrigger(hour=schedule["hour"], minute=schedule["minute"]),
        id=schedule["id"],
        replace_existing=True
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data = load_data()
    schedules = data.get("schedules", [])

    if not schedules:
        await update.message.reply_text("📭 Hech qanday rejalashtirilgan post yo'q.")
        return

    type_icons = {
        "photo": "🖼", "video": "🎥", "audio": "🎵",
        "document": "📄", "animation": "🎞", "voice": "🎤", "video_note": "⭕"
    }

    text = "📋 *Rejalashtirilgan postlar:*\n\n"
    for i, s in enumerate(schedules, 1):
        icon = type_icons.get(s["file_type"], "📎")
        text += f"{i}. {icon} — ⏰ {s['hour']:02d}:{s['minute']:02d}\n"
        if s.get("caption"):
            text += f"   📝 _{s['caption'][:30]}..._\n" if len(s['caption']) > 30 else f"   📝 _{s['caption']}_\n"
        text += f"   🆔 `{s['id']}`\n\n"

    text += "🗑 O'chirish uchun: `/delete ID`"
    await update.message.reply_text(text, parse_mode="Markdown")

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "❌ ID kiriting!\nMisol: `/delete post_0900_0`\n\n"
            "IDlarni ko'rish: /list",
            parse_mode="Markdown"
        )
        return

    schedule_id = context.args[0]
    data = load_data()
    schedules = data.get("schedules", [])

    found = False
    for s in schedules:
        if s["id"] == schedule_id:
            found = True
            schedules.remove(s)
            break

    if not found:
        await update.message.reply_text(f"❌ `{schedule_id}` topilmadi!", parse_mode="Markdown")
        return

    data["schedules"] = schedules
    save_data(data)

    if scheduler.get_job(schedule_id):
        scheduler.remove_job(schedule_id)

    await update.message.reply_text(f"✅ `{schedule_id}` o'chirildi!", parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data = load_data()
    count = len(data.get("schedules", []))
    jobs = len(scheduler.get_jobs())
    now = datetime.now(pytz.timezone(TIMEZONE))

    await update.message.reply_text(
        f"🤖 *Bot holati:* Ishlayapti ✅\n\n"
        f"📅 Hozirgi vaqt: `{now.strftime('%d.%m.%Y %H:%M')}` (UZ)\n"
        f"📋 Jami postlar: `{count}` ta\n"
        f"⚙️ Faol vazifalar: `{jobs}` ta\n"
        f"📢 Kanal: `{CHANNEL_ID}`",
        parse_mode="Markdown"
    )

async def post_init(application):
    data = load_data()
    for s in data.get("schedules", []):
        add_job_to_scheduler(application, s)
    scheduler.start()
    logger.info(f"{len(data.get('schedules', []))} ta jadval yuklandi")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN muhit o'zgaruvchisi yo'q!")
    if not CHANNEL_ID:
        raise ValueError("CHANNEL_ID muhit o'zgaruvchisi yo'q!")
    if not ADMIN_ID:
        raise ValueError("ADMIN_ID muhit o'zgaruvchisi yo'q!")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.AUDIO |
        filters.Document.ALL | filters.ANIMATION |
        filters.VOICE | filters.VIDEO_NOTE,
        receive_file
    ))

    logger.info("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
