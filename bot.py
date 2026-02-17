#!/usr/bin/env python3
"""
Telegram AI Assistant Bot using OpenRouter (Qwen model)
Polling mode, no webhook.
"""

import asyncio
import logging
import os
import sys
from typing import Optional

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

# --- Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

if not BOT_TOKEN or not OPENROUTER_API_KEY:
    logging.critical("Missing BOT_TOKEN or OPENROUTER_API_KEY environment variables.")
    sys.exit(1)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "qwen/qwen-2-7b-instruct"
SYSTEM_PROMPT = "You are EJDevAssistant, an expert coding AI. Provide clear, correct, production-ready code."

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- OpenRouter API call (synchronous, run in thread) ---
def call_openrouter(user_message: str) -> Optional[str]:
    """Call OpenRouter API and return assistant reply or None on failure."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    }
    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # Extract assistant message
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
        return None

# --- Helper: split long messages (Telegram limit 4096) ---
def split_message(text: str, max_len: int = 4096):
    """Split long message into chunks respecting line breaks if possible."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while len(text) > max_len:
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks

# --- Handlers ---
async def start(update: Update, context):
    """Send welcome message with inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🤖 Ask AI", callback_data="ask_ai"),
            InlineKeyboardButton("🧠 About Bot", callback_data="about"),
        ],
        [
            InlineKeyboardButton("💼 Developer Info", callback_data="dev"),
            InlineKeyboardButton("📞 Contact Developer", callback_data="contact"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to EJDevAssistant! Choose an option:",
        reply_markup=reply_markup,
    )

async def button_callback(update: Update, context):
    """Handle inline button presses."""
    query = update.callback_query
    await query.answer()  # acknowledge callback

    data = query.data
    chat_id = query.message.chat_id

    if data == "ask_ai":
        text = "AI mode enabled. Send your coding question."
    elif data == "about":
        text = "EJDevAssistant is a coding AI powered by Qwen."
    elif data == "dev":
        text = (
            "Developer: Eshan\n"
            "Country: Sri Lanka\n"
            "Skills: Software Engineering, AI Development, Web Development, Crypto & Forex Trading"
        )
    elif data == "contact":
        text = (
            "Telegram: @ejag78X\n"
            "X: @EJDavX\n"
            "Email: ejfxprotrade@gmail.com"
        )
    else:
        text = "Unknown option."

    await context.bot.send_message(chat_id=chat_id, text=text)

async def handle_message(update: Update, context):
    """Process any text message (non‑command) via OpenRouter AI."""
    user_text = update.message.text
    logger.info(f"Message from {update.effective_user.id}: {user_text[:50]}...")

    # Indicate typing while waiting
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Run the blocking API call in a thread to not block the event loop
    loop = asyncio.get_running_loop()
    reply_content = await loop.run_in_executor(None, call_openrouter, user_text)

    if reply_content is None:
        await update.message.reply_text(
            "⚠️ AI service temporarily unavailable. Please try again."
        )
        return

    # Split and send
    for chunk in split_message(reply_content):
        await update.message.reply_text(chunk)

async def error_handler(update: Update, context):
    """Log errors and notify user if possible."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "An internal error occurred. Please try again later."
        )

def main():
    """Start the bot."""
    # Create Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Register error handler
    application.add_error_handler(error_handler)

    # Start polling (no webhook)
    logger.info("Bot started in polling mode.")
    application.run_polling()

if __name__ == "__main__":
    main()
