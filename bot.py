import logging
import os
import asyncio
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ChatAction

# --- Configuration ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not BOT_TOKEN or not OPENROUTER_API_KEY:
    raise ValueError("Missing BOT_TOKEN or OPENROUTER_API_KEY environment variables")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-coder"
SYSTEM_PROMPT = (
    "You are an expert software engineer. "
    "Fix bugs and generate clean production-ready Python, Java, JavaScript, HTML, CSS code. "
    "Always return formatted markdown code blocks. "
    "Be direct and professional. Do not add unnecessary explanations."
)

# --- AI Query Function ---
def query_ai_sync(prompt: str) -> str:
    """Synchronous function to call OpenRouter API."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 2000
    }
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"AI query failed: {e}")
        raise

async def query_ai(prompt: str) -> str:
    """Async wrapper for query_ai_sync using to_thread."""
    return await asyncio.to_thread(query_ai_sync, prompt)

# --- Helper Functions ---
def extract_clean_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """Extract text without bot mention if bot is mentioned. Returns None if not mentioned."""
    message = update.effective_message
    if not message or not message.text or not message.entities:
        return None

    bot_username = context.bot.username.lower()
    text = message.text
    entities = message.entities

    # Check if any mention entity points to this bot
    for entity in entities:
        if entity.type == "mention":
            mention = text[entity.offset:entity.offset+entity.length]
            if mention.lower() == f"@{bot_username}":
                # Remove the mention from the text (strip it)
                clean = text[:entity.offset] + text[entity.offset+entity.length:]
                return clean.strip()

    return None

async def send_typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send typing indicator."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🔧 Fix Code", callback_data="fix"),
            InlineKeyboardButton("🧠 Generate Code", callback_data="generate"),
        ],
        [
            InlineKeyboardButton("📖 Help", callback_data="help"),
            InlineKeyboardButton("📞 Contact", callback_data="contact"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome to AI Coding Bot!\n\n"
        "Mention me in a group with your coding request.\n"
        "Example: `@{} fix this python code: print(\"hello`".format(context.bot.username),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show usage instructions."""
    text = (
        "📖 *How to use:*\n"
        "Mention the bot in a group with your request.\n\n"
        "*Examples:*\n"
        "`@{} fix this Python code:`\n"
        "`print(\"hello`\n\n"
        "`@{} generate HTML login page`\n\n"
        "Supported languages: Python, Java, JavaScript, HTML, CSS"
    ).format(context.bot.username, context.bot.username)
    await update.message.reply_text(text, parse_mode="Markdown")

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show contact info."""
    text = (
        "📞 *Contact*\n"
        "Telegram: @ejag78\n"
        "Email: ejfxprotrade@gmail.com"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == "fix":
        text = "Please mention me in a group with the code you want to fix.\nExample: `@{} fix this ...`".format(context.bot.username)
    elif query.data == "generate":
        text = "Please mention me in a group with your code generation request.\nExample: `@{} generate ...`".format(context.bot.username)
    elif query.data == "help":
        text = (
            "📖 *How to use:*\n"
            "Mention the bot in a group with your request.\n\n"
            "*Examples:*\n"
            "`@{} fix this Python code:`\n"
            "`print(\"hello`\n\n"
            "`@{} generate HTML login page`"
        ).format(context.bot.username, context.bot.username)
    elif query.data == "contact":
        text = "📞 *Contact*\nTelegram: @ejag78\nEmail: ejfxprotrade@gmail.com"
    else:
        text = "Unknown option."

    await query.edit_message_text(text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process messages: respond only if bot is mentioned."""
    # Ignore bot's own messages
    if update.effective_user and update.effective_user.is_bot:
        return

    clean_prompt = extract_clean_text(update, context)
    if clean_prompt is None:
        return  # bot not mentioned

    # Show typing indicator
    await send_typing(update, context)

    try:
        # Get AI response
        ai_response = await query_ai(clean_prompt)
        # Send response with Markdown
        await update.message.reply_text(ai_response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await update.message.reply_text(
            "❌ Sorry, an error occurred while processing your request. Please try again later."
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and notify user."""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "An unexpected error occurred. Please try again later."
        )

# --- Main ---
def main():
    """Start the bot."""
    # Create Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("contact", contact))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    # Start polling
    logger.info("Bot started polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
