import os
import logging
import asyncio
from flask import Flask, request, jsonify
from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# -------------------- Configuration --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

REQUIRED_ENV_VARS = ["BOT_TOKEN", "GROQ_API_KEY", "WEBHOOK_URL", "PORT"]
missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing:
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

# -------------------- Logging --------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- Developer Info --------------------
DEV_INFO = {
    "name": "Eshan",
    "country": "Sri Lanka",
    "skills": "Software Engineering, AI, Web, Crypto & Forex",
    "tg": "@ejag78X",
    "x": "@EJDavX",
    "email": "ejfxprotrade@gmail.com"
}


def get_developer_info() -> str:
    return (
        f"*👤 Developer Information*\n\n"
        f"*Developer Name:* {DEV_INFO['name']}\n"
        f"*Country:* {DEV_INFO['country']}\n"
        f"*Skills:* {DEV_INFO['skills']}\n\n"
        f"*Telegram:* {DEV_INFO['tg']}\n"
        f"*X:* {DEV_INFO['x']}\n"
        f"*Email:* {DEV_INFO['email']}"
    )


def ask_ai(prompt: str) -> str:
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are EJDevAssistant, an expert coding AI."},
                {"role": "user", "content": prompt}
            ]
        )

        return completion.choices[0].message.content

    except Exception as e:
        print("Groq Error:", e)
        return "⚠️ AI service temporarily unavailable. Please try again."


# -------------------- Telegram Handlers --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with inline keyboard."""
    keyboard = [
        [InlineKeyboardButton("🤖 Ask AI", callback_data="ask_ai")],
        [InlineKeyboardButton("🧠 About Bot", callback_data="about")],
        [InlineKeyboardButton("💼 Developer Info", callback_data="dev_info")],
        [InlineKeyboardButton("📞 Contact Developer", callback_data="contact")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome to ejdevassistant_bot!\n\n"
        "I am your AI assistant powered by Groq. Send me any text and I'll respond directly.",
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    help_text = (
        "📚 *Help*\n\n"
        "/start - Show main menu\n"
        "/help - Show this help\n\n"
        "You can send any text directly and I'll reply with Groq AI."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == "ask_ai":
        await query.edit_message_text(
            "✅ AI mode is ready. Send me any message and I'll respond using Groq AI.\n\n"
            "Use /start to return to the main menu.",
            parse_mode=ParseMode.MARKDOWN
        )
    elif query.data == "about":
        about_text = (
            "🧠 *About This Bot*\n\n"
            "This is an AI assistant powered by Groq, designed to help with coding and more.\n"
            "Built by Eshan, a Software Engineer from Sri Lanka.\n"
            "Hosted securely on Railway."
        )
        await query.edit_message_text(about_text, parse_mode=ParseMode.MARKDOWN)
    elif query.data == "dev_info":
        await query.edit_message_text(get_developer_info(), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "contact":
        contact_text = (
            "📞 *Contact Developer*\n\n"
            f"{get_developer_info()}"
        )
        await query.edit_message_text(contact_text, parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages and return AI output directly."""
    user_text = update.message.text
    response = ask_ai(user_text)
    await update.message.reply_text(response)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")


# -------------------- Flask Webhook Setup --------------------
app = Flask(__name__)

# Build Telegram Application
telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CallbackQueryHandler(button_handler))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_error_handler(error_handler)

# Initialize once at startup so webhook updates can be processed immediately
asyncio.run(telegram_app.initialize())


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Telegram updates."""
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
    return "OK", 200


# -------------------- Main --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
