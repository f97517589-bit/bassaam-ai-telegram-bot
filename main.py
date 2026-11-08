import logging
import os
from typing import List, Dict

from dotenv import load_dotenv
from groq import AsyncGroq
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

from db import init_db, add_message, get_history, clear_history, get_stats

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
ADMIN_IDS = {
    int(item.strip())
    for item in os.getenv("ADMIN_IDS", "").split(",")
    if item.strip().isdigit()
}

SYSTEM_PROMPT = """أنت مساعد ذكي ودود ودقيق. أجب بلغة المستخدم، ويمكنك التحدث باللهجة اليمنية عند طلبها.
اشرح المعلومات بوضوح وبأسلوب مناسب للطلاب. إذا لم تكن متأكداً من معلومة فصرّح بذلك ولا تخترع إجابة.
في الأسئلة الطبية أو العلمية، قدّم معلومات تعليمية عامة ونبّه إلى ضرورة الرجوع لمختص عند الحاجة.
لا تدّعِ أنك إنسان أو أنك تملك معلومات غير متاحة لك."""

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("ai-telegram-bot")

client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"أهلاً {user.first_name} 👋\n\n"
        "أنا المساعد الذكي 🤖\n"
        "أرسل سؤالك وسأحاول مساعدتك.\n\n"
        "الأوامر المتاحة:\n"
        "/new — بدء محادثة جديدة\n"
        "/help — المساعدة"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💬 أرسل أي سؤال كنص عادي.\n"
        "/new — مسح سياق محادثتك والبدء من جديد\n"
        "/help — عرض هذه المساعدة\n\n"
        "حالياً أستقبل الرسائل النصية فقط."
    )


async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_history(update.effective_user.id)
    await update.message.reply_text("بدأنا محادثة جديدة ✨ تم مسح سياق المحادثة السابقة.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    if not user_text:
        return
    if len(user_text) > 12000:
        await update.message.reply_text("الرسالة طويلة جداً. اختصرها إلى 12,000 حرف كحد أقصى.")
        return
    if client is None:
        await update.message.reply_text("الخدمة غير مكتملة الإعداد. يرجى إبلاغ المشرف.")
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    history: List[Dict[str, str]] = get_history(user_id, limit=12)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    try:
        completion = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_completion_tokens=1800,
        )
        answer = completion.choices[0].message.content or "لم أتمكن من صياغة إجابة."
        add_message(user_id, "user", user_text)
        add_message(user_id, "assistant", answer)

        # Telegram message length limit is 4096 characters.
        for start_index in range(0, len(answer), 4000):
            await update.message.reply_text(answer[start_index:start_index + 4000])
    except Exception:
        logger.exception("AI request failed")
        await update.message.reply_text(
            "عذراً، تعذّر الحصول على رد من خدمة الذكاء الاصطناعي الآن. "
            "حاول مرة أخرى بعد قليل."
        )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("هذا الأمر مخصص للمشرف فقط.")
        return
    users, messages = get_stats()
    await update.message.reply_text(
        f"📊 إحصائيات البوت\n\n👥 المستخدمون: {users}\n💬 الرسائل المحفوظة: {messages}"
    )


async def post_init(application: Application):
    init_db()
    logger.info("Database initialized")


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY environment variable")

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_chat))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
