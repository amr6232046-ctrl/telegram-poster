import os
import logging
from datetime import datetime, timezone, timedelta
import json

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

TZ_OFFSET = timedelta(hours=5)
TZ = timezone(TZ_OFFSET)

STORAGE_FILE = "scheduled_files.json"

def now_tashkent():
    return datetime.now(TZ)

def load_data():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r") as f:
            return json.load(f)
    return {"schedules": []}

def save_data(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)

scheduler = AsyncIOScheduler(timezone=TZ)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return

    text = (
        "👋 *Kanal Auto-Post Boti*\n\n"
        "📌 *Qanday ishlatiladi:*\n\n"
        "1️⃣ Menga rasm/video/fayl yuboring\n"
        "2️⃣ Keyin vaqt belgilang: `/schedule 09:00`\n"
        "3️⃣ O'sha vaqtda 1 marta kanalga yuboradi\n\n"
        "📋 *Buyruqlar:*\n"
        "/list — kutayotgan postlar\n"
        "/cancel — oxirgi postni bekor qilish\n"
        "/status — bot holati va hozirgi vaqt\n"
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
        "photo": "🖼 Rasm", "video": "🎥 Video", "audio": "🎵 Musiqa",
        "document": "📄 Fayl", "animation": "🎞 GIF",
        "voice": "🎤 Ovozli", "video_note": "⭕ Video doira"
    }

    now = now_tashkent()
    await msg.reply_text(
        f"✅ *{type_names.get(file_type, 'Fayl')}* qabul qilindi!\n\n"
        f"🕐 Hozir Toshkent vaqti: *{now.strftime('%H:%M')}*\n\n"
        f"⏰ Vaqt belgilang: `/schedule 14:30`",
        parse_mode="Markdown"
    )

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("❌ Misol: `/schedule 14:30`", parse_mode="Markdown")
        return

    time_str = context.args[0]
    try:
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ To'g'ri format: `14:30`", parse_mode="Markdown")
        return

    pending = context.user_data.get("pending_file")
    if not pending:
        await update.message.reply_text("❌ Avval fayl yuboring!")
        return

    now = now_tashkent()
    send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if send_time <= now:
        await update.message.reply_text(
            f"❌ Bu vaqt o'tib ketgan!\n"
            f"🕐 Hozir: *{now.strftime('%H:%M')}*\n"
            f"Kelajakdagi vaqt kiriting.",
            parse_mode="Markdown"
        )
        return

    data = load_data()
    schedule_id = f"once_{hour:02d}{minute:02d}_{len(data['schedules'])}"

    new_schedule = {
        "id": schedule_id,
        "file_id": pending["file_id"],
        "file_type": pending["file_type"],
        "caption": pending["caption"],
        "hour": hour,
        "minute": minute,
        "send_time": send_time.isoformat()
    }

    data["schedules"].append(new_schedule)
    save_data(data)
    add_once_job(context.application, new_schedule, send_time)
    context.user_data.pop("pending_file", None)

    await update.message.reply_text(
        f"✅ *Tayyor!*\n\n"
        f"⏰ Yuborish vaqti: *{hour:02d}:{minute:02d}* (Toshkent)\n"
        f"📢 Kanal: `{CHANNEL_ID}`\n"
        f"🔔 Faqat 1 marta yuboriladi va tamom",
        parse_mode="Markdown"
    )

def add_once_job(app, schedule, send_time):
    async def send_and_delete():
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

            data = load_data()
            data["schedules"] = [s for s in data["schedules"] if s["id"] != schedule["id"]]
            save_data(data)

            await bot.send_message(chat_id=ADMIN_ID, text=f"✅ Post yuborildi! Kanal: {CHANNEL_ID}")
            logger.info(f"Post yuborildi: {schedule['id']}")

        except Exception as e:
            logger.error(f"Xato: {e}")
            try:
                await app.bot.send_message(chat_id=ADMIN_ID, text=f"❌ Xato: {e}")
            except:
                pass

    scheduler.add_job(
        send_and_delete,
        DateTrigger(run_date=send_time),
        id=schedule["id"],
        replace_existing=True
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data = load_data()
    schedules = data.get("schedules", [])

    if not schedules:
        await update.message.reply_text("📭 Kutayotgan post yo'q.")
        return

    type_icons = {
        "photo": "🖼", "video": "🎥", "audio": "🎵",
        "document": "📄", "animation": "🎞", "voice": "🎤", "video_note": "⭕"
    }
    text = "📋 *Kutayotgan postlar:*\n\n"
    for i, s in enumerate(schedules, 1):
        icon = type_icons.get(s["file_type"], "📎")
        text += f"{i}. {icon} — ⏰ {s['hour']:02d}:{s['minute']:02d} (Toshkent)\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data = load_data()
    if not data["schedules"]:
        await update.message.reply_text("📭 Bekor qilish uchun post yo'q.")
        return

    last = data["schedules"].pop()
    save_data(data)
    if scheduler.get_job(last["id"]):
        scheduler.remove_job(last["id"])

    await update.message.reply_text(f"✅ Bekor qilindi: ⏰ {last['hour']:02d}:{last['minute']:02d}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data = load_data()
    count = len(data.get("schedules", []))
    now = now_tashkent()

    await update.message.reply_text(
        f"🤖 *Bot holati:* Ishlayapti ✅\n\n"
        f"🕐 Toshkent vaqti: *{now.strftime('%H:%M')}*\n"
        f"📋 Kutayotgan postlar: *{count}* ta\n"
        f"📢 Kanal: `{CHANNEL_ID}`",
        parse_mode="Markdown"
    )

async def post_init(application):
    now = now_tashkent()
    data = load_data()
    valid = []
    for s in data.get("schedules", []):
        send_time = datetime.fromisoformat(s["send_time"])
        if send_time > now:
            add_once_job(application, s, send_time)
            valid.append(s)
    data["schedules"] = valid
    save_data(data)
    scheduler.start()
    logger.info(f"Bot ishga tushdi. {len(valid)} ta post kutmoqda.")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN yo'q!")
    if not CHANNEL_ID:
        raise ValueError("CHANNEL_ID yo'q!")
    if not ADMIN_ID:
        raise ValueError("ADMIN_ID yo'q!")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.AUDIO |
        filters.Document.ALL | filters.ANIMATION |
        filters.VOICE | filters.VIDEO_NOTE,
        receive_file
    ))

    logger.info("Bot polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
