import os
import logging
import asyncio
from functools import partial

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ---------- Environment variables ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set.")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable not set.")

# ---------- DeepSeek configuration ----------
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
SYSTEM_PROMPT = (
    "You are EJDevAssistant, an expert AI coding assistant. "
    "You generate and fix production-ready code. "
    "You support Python, JavaScript, Java, HTML, CSS. "
    "Always return clean markdown code blocks. "
    "Be concise and professional."
)
TEMPERATURE = 0.2
MAX_TOKENS = 2000

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- Helper: DeepSeek API call (blocking, run in executor) ----------
def _call_deepseek_sync(prompt: str) -> str:
    """Synchronous DeepSeek API call using requests."""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        raise  # re-raise to be handled in async wrapper

async def call_deepseek(prompt: str) -> str:
    """Asynchronous wrapper for DeepSeek API call."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _call_deepseek_sync, prompt)

# ---------- Inline keyboard ----------
def get_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🔧 Fix Code", callback_data="fix"),
            InlineKeyboardButton("🧠 Generate Code", callback_data="generate"),
        ],
        [
            InlineKeyboardButton("📖 Help", callback_data="help"),
            InlineKeyboardButton("📞 Contact", callback_data="contact"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------- Command handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to EJDevAssistant!\n\n"
        "I can help you fix or generate code. Mention me in a group with your request.",
        reply_markup=get_main_keyboard(),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *How to use me:*\n\n"
        "• In a group, mention me followed by your request.\n"
        "  Example: `@EJDevAssistant fix this Python error: ...`\n"
        "• Use /start to see the main menu.\n"
        "• Use /contact to get owner info."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact_text = (
        "📞 *Contact Information*\n\n"
        "Telegram: @ejag78\n"
        "Email: ejfxprotrade@gmail.com"
    )
    await update.message.reply_text(contact_text, parse_mode="Markdown")

# ---------- Callback query handler ----------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "fix":
        text = (
            "🔧 *Fix Code*\n\n"
            "Mention me in a group with the code you need fixed.\n"
            "Example: `@EJDevAssistant fix this function: ...`"
        )
    elif data == "generate":
        text = (
            "🧠 *Generate Code*\n\n"
            "Mention me in a group with the description of the code you need.\n"
            "Example: `@EJDevAssistant generate a Python function to sort a list`"
        )
    elif data == "help":
        text = (
            "📖 *Help*\n\n"
            "• Mention me in a group with your request.\n"
            "• Use /start to see the main menu.\n"
            "• Use /contact to get owner info."
        )
    elif data == "contact":
        text = (
            "📞 *Contact*\n\n"
            "Telegram: @ejag78\n"
            "Email: ejfxprotrade@gmail.com"
        )
    else:
        text = "Unknown option."

    await query.edit_message_text(text, parse_mode="Markdown")

# ---------- Message handler for groups (mention only) ----------
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    # Ignore messages from other bots
    if message.from_user.is_bot:
        return

    bot_username = context.bot.username.lower()
    text = message.text

    # Check if the bot is mentioned via entities
    mentioned = False
    prompt = None
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention = text[entity.offset : entity.offset + entity.length]
                if mention.lower() == f"@{bot_username}":
                    mentioned = True
                    # Remove the mention and any following whitespace
                    prompt = text[:entity.offset] + text[entity.offset + entity.length :]
                    prompt = prompt.strip()
                    break

    if not mentioned:
        return

    if not prompt:
        prompt = "Hello"  # fallback if only mention

    # Send typing indicator
    await context.bot.send_chat_action(
        chat_id=message.chat_id, action=ChatAction.TYPING
    )

    try:
        # Call DeepSeek API
        response = await call_deepseek(prompt)
        await message.reply_text(response, parse_mode="Markdown")
    except Exception:
        await message.reply_text("⚠️ AI request failed. Try again.")

# ---------- Error handler ----------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

# ---------- Main ----------
def main():
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("contact", contact))

    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))

    # Add message handler for groups (mention only)
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            handle_group_message,
        )
    )

    # Add error handler
    application.add_error_handler(error_handler)

    # Start polling
    logger.info("Starting EJDevAssistant...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
