# bot.py
import os
import logging
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("BOT_TOKEN and GROQ_API_KEY must be set in environment variables.")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "qwen-3-32b"  # Ensure this model is available; fallback to "mixtral-8x7b-32768" if needed

SYSTEM_PROMPT = (
    "You are an expert software engineer. "
    "Fix bugs and generate clean production-ready Python, Java, JavaScript, HTML, CSS code. "
    "Always return formatted markdown code blocks. "
    "Be direct and professional. "
    "Do not add unnecessary explanations."
)

async def query_groq(messages):
    """Send a request to Groq API (non-blocking using asyncio.to_thread)."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2048
    }
    try:
        # Run requests.post in a thread to avoid blocking
        response = await asyncio.to_thread(requests.post, GROQ_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return f"⚠️ Sorry, an error occurred while processing your request: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message with inline keyboard."""
    keyboard = [
        [InlineKeyboardButton("🔧 Fix Code", callback_data="fix")],
        [InlineKeyboardButton("🧠 Generate Code", callback_data="generate")],
        [InlineKeyboardButton("📖 Help", callback_data="help")],
        [InlineKeyboardButton("📞 Contact", callback_data="contact")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Hello! I'm an AI coding assistant. Mention me in a group with your request.\n\n"
        "Example:\n"
        "`@YourBotUsername fix this Python code: print('hello`'\n\n"
        "Or use the buttons below for more info.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help text."""
    help_text = (
        "🤖 *How to use me:*\n"
        "Mention me in a group with your request. I'll reply with fixed or generated code.\n\n"
        "*Examples:*\n"
        "`@YourBotUsername fix this Python code: print('hello`'\n"
        "`@YourBotUsername generate HTML login page`\n"
        "`@YourBotUsername explain error: syntax error near unexpected token`\n\n"
        "Supported languages: Python, Java, JavaScript, HTML, CSS."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show contact information."""
    contact_text = (
        "📞 *Contact*\n"
        "Telegram: @ejag78\n"
        "Email: ejfxprotrade@gmail.com"
    )
    await update.message.reply_text(contact_text, parse_mode="Markdown")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == "fix":
        await query.edit_message_text(
            "🔧 To fix code, mention me with your code.\n\n"
            "Example:\n"
            "`@YourBotUsername fix this Python code: print('hello`'",
            parse_mode="Markdown"
        )
    elif query.data == "generate":
        await query.edit_message_text(
            "🧠 To generate code, mention me with your request.\n\n"
            "Example:\n"
            "`@YourBotUsername generate a Python function to reverse a string`",
            parse_mode="Markdown"
        )
    elif query.data == "help":
        help_text = (
            "🤖 *How to use me:*\n"
            "Mention me in a group with your request. I'll reply with fixed or generated code.\n\n"
            "*Examples:*\n"
            "`@YourBotUsername fix this Python code: print('hello`'\n"
            "`@YourBotUsername generate HTML login page`\n"
            "`@YourBotUsername explain error: syntax error near unexpected token`\n\n"
            "Supported languages: Python, Java, JavaScript, HTML, CSS."
        )
        await query.edit_message_text(help_text, parse_mode="Markdown")
    elif query.data == "contact":
        contact_text = (
            "📞 *Contact*\n"
            "Telegram: @ejag78\n"
            "Email: ejfxprotrade@gmail.com"
        )
        await query.edit_message_text(contact_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages that mention the bot."""
    # Ignore messages from the bot itself
    if update.effective_user and update.effective_user.id == context.bot.id:
        return

    message = update.message
    if not message or not message.text:
        return

    # Check if bot is mentioned
    bot_username = context.bot.username
    mention_detected = False
    clean_text = message.text

    # Check entities for mention
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mentioned = message.text[entity.offset:entity.offset+entity.length]
                if mentioned == f"@{bot_username}":
                    mention_detected = True
                    # Remove the mention from the text (including possible whitespace after)
                    clean_text = message.text[:entity.offset] + message.text[entity.offset+entity.length:].lstrip()
                    break

    if not mention_detected:
        return  # Ignore if not mentioned

    if not clean_text.strip():
        await message.reply_text("Please provide a request after mentioning me.")
        return

    # Prepare messages for AI
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": clean_text}
    ]

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Query Groq
    response_text = await query_groq(messages)

    # Reply with markdown
    await message.reply_text(response_text, parse_mode="Markdown")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Start the bot."""
    # Create Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("contact", contact_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    application.add_error_handler(error_handler)

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
