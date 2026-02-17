import os
import logging
import asyncio
import requests
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# -------------------- Configuration --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

REQUIRED_ENV_VARS = ["BOT_TOKEN", "DEEPSEEK_API_KEY", "WEBHOOK_URL"]
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
    "field": "Software Engineering",
    "specialties": "AI Development, Web Development, Crypto Trading, Forex Trading",
    "tg": "@ejag78X",
    "x": "@EJDavX",
    "email": "ejfxprotrade@gmail.com"
}

def get_developer_info() -> str:
    return (
        f"*👤 Developer Information*\n\n"
        f"*Name:* {DEV_INFO['name']}\n"
        f"*Country:* {DEV_INFO['country']}\n"
        f"*Field:* {DEV_INFO['field']}\n"
        f"*Specialties:* {DEV_INFO['specialties']}\n\n"
        f"*Telegram:* {DEV_INFO['tg']}\n"
        f"*X (Twitter):* {DEV_INFO['x']}\n"
        f"*Email:* {DEV_INFO['email']}"
    )

# -------------------- In-Memory Storage --------------------
# user_sessions: stores conversation history (list of messages with role and content)
user_sessions = {}
# user_ai_mode: tracks if user is in AI chat mode
user_ai_mode = {}

# -------------------- DeepSeek API Integration --------------------
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
TIMEOUT = 30

def get_ai_response(user_id: int, message_text: str) -> str:
    """Call DeepSeek API with conversation history and return response."""
    # Initialize history if not exists
    if user_id not in user_sessions:
        user_sessions[user_id] = []
    history = user_sessions[user_id]

    # Append user message
    history.append({"role": "user", "content": message_text})
    # Trim history to last 10 messages
    if len(history) > 10:
        history = history[-10:]
        user_sessions[user_id] = history

    # Prepare API payload
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": history,
        "stream": False
    }

    try:
        response = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        assistant_msg = data["choices"][0]["message"]["content"]

        # Append assistant response to history
        history.append({"role": "assistant", "content": assistant_msg})
        # Trim again
        if len(history) > 10:
            history = history[-10:]
            user_sessions[user_id] = history

        return assistant_msg
    except Exception as e:
        logger.error(f"DeepSeek API error for user {user_id}: {e}")
        return "AI service temporarily unavailable."

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
        "I am your AI assistant powered by DeepSeek. Use the buttons below to get started.",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    help_text = (
        "📚 *Help*\n\n"
        "/start - Show main menu\n"
        "/help - Show this help\n\n"
        "Press '🤖 Ask AI' to enter AI chat mode. In AI mode, just send any message and I'll reply with AI-generated content.\n"
        "Use the other buttons to learn more about the bot and its developer."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "ask_ai":
        user_ai_mode[user_id] = True
        await query.edit_message_text(
            "✅ You are now in AI mode. Send me any message and I'll respond using DeepSeek AI.\n\n"
            "Use /start to return to the main menu.",
            parse_mode=ParseMode.MARKDOWN
        )
    elif query.data == "about":
        about_text = (
            "🧠 *About This Bot*\n\n"
            "This is an AI assistant powered by DeepSeek, designed to help with various tasks.\n"
            "Built by Eshan, a Software Engineer from Sri Lanka.\n"
            "Hosted securely on Railway."
        )
        await query.edit_message_text(about_text, parse_mode=ParseMode.MARKDOWN)
    elif query.data == "dev_info":
        await query.edit_message_text(get_developer_info(), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "contact":
        contact_text = (
            "📞 *Contact Developer*\n\n"
            "You can reach out via the following channels:\n\n"
            f"{get_developer_info()}"
        )
        await query.edit_message_text(contact_text, parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    user_id = update.effective_user.id
    text = update.message.text

    # Check if user is in AI mode
    if user_ai_mode.get(user_id, False):
        # Send typing action
        await context.bot.send_chat_action(chat_id=user_id, action="typing")
        # Get AI response
        response = get_ai_response(user_id, text)
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        # Not in AI mode: suggest to use /start
        await update.message.reply_text(
            "Please use /start to access the main menu and select an option."
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

# -------------------- Flask Webhook Setup --------------------
flask_app = Flask(__name__)

# Build Telegram Application
telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CallbackQueryHandler(button_handler))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_error_handler(error_handler)

@flask_app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200

@flask_app.route(f"/webhook", methods=["POST"])
def webhook():
    """Handle incoming Telegram updates."""
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, telegram_app.bot)
        # Process update asynchronously
        asyncio.run(telegram_app.process_update(update))
        return "OK", 200
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return "Error", 500

def set_webhook():
    """Set the webhook URL for the bot."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}/webhook"
    try:
        response = requests.get(url)
        response.raise_for_status()
        logger.info(f"Webhook set to {WEBHOOK_URL}/webhook")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        raise

# -------------------- Main --------------------
if __name__ == "__main__":
    # Set webhook
    set_webhook()
    # Run Flask app
    flask_app.run(host="0.0.0.0", port=PORT)
