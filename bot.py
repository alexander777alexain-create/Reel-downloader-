import os
import logging
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_URL = os.environ.get('API_URL', 'https://insta-download-sepia.vercel.app/api/download')
DEVELOPER_USERNAME = os.environ.get('DEVELOPER_USERNAME', 'teamkohinoor')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- HELPERS ----------
def extract_instagram_url(text):
    pattern = r'(https?://(?:www\.)?instagram\.com/(?:reel|p|tv|stories)/[a-zA-Z0-9_-]+(?:\?[^\s]*)?)'
    match = re.search(pattern, text)
    return match.group(1) if match else None

def fetch_media(url, quality='high'):
    try:
        resp = requests.get(API_URL, params={'url': url, 'quality': quality}, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return {'error': f'API returned {resp.status_code}'}
    except requests.Timeout:
        return {'error': '⏳ Timeout — try low quality'}
    except Exception as e:
        return {'error': str(e)}

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (
        f"👋 Hello {user.first_name}!\n\n"
        "Send me any Instagram link and I'll download it.\n\n"
        "📌 Supported: Reels, Posts, Carousels, Stories\n"
        "🎯 Select quality when you send a link."
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *How to use:*\n\n"
        "1️⃣ Send Instagram link\n"
        "2️⃣ Bot shows quality buttons\n"
        "3️⃣ Select quality → video sent\n\n"
        "*Commands:*\n"
        "/start — Welcome\n"
        "/help — This message\n"
        "/about — Bot info"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Instagram Downloader Bot*\n\n"
        "Built with ❤️ for KOHINOOR\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# ---------- MESSAGE HANDLER ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    url = extract_instagram_url(text)
    if not url:
        await update.message.reply_text("❌ No Instagram link found.")
        return

    keyboard = [
        [
            InlineKeyboardButton("🔽 Low", callback_data=f"quality_low_{url}"),
            InlineKeyboardButton("🟡 Medium", callback_data=f"quality_medium_{url}"),
            InlineKeyboardButton("🔼 High", callback_data=f"quality_high_{url}")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    await update.message.reply_text(
        "🎯 *Select video quality:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- CALLBACKS ----------
async def quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "cancel":
        await query.edit_message_text("❌ Cancelled.")
        return

    parts = data.split('_', 2)
    if len(parts) < 3:
        await query.edit_message_text("❌ Invalid request.")
        return

    quality = parts[1]
    url = parts[2]
    await query.edit_message_text(f"⏳ Fetching video in *{quality.upper()}*...", parse_mode='Markdown')

    result = fetch_media(url, quality)
    if result.get('success'):
        video_url = result.get('video_url')
        username = result.get('username', 'Unknown')
        caption_text = result.get('caption', '')[:200]

        caption = f"🎬 *{username}*\n\n{caption_text}\n\n📊 Quality: *{quality.upper()}*"
        keyboard = [
            [
                InlineKeyboardButton("📥 Download", url=video_url),
                InlineKeyboardButton("🔄 Change Quality", callback_data=f"changequality_{url}")
            ],
            [
                InlineKeyboardButton("ℹ️ Info", callback_data=f"info_{url}"),
                InlineKeyboardButton("🔁 Re-download", callback_data=f"redownload_{quality}_{url}")
            ],
            [InlineKeyboardButton(f"👨‍💻 Developer", callback_data="developer")]
        ]
        try:
            await query.message.reply_video(
                video=video_url,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard),
                supports_streaming=True
            )
            await query.edit_message_text("✅ Video sent!")
        except Exception:
            await query.message.reply_document(
                document=video_url,
                caption=f"📁 {username}\n\n{caption_text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await query.edit_message_text("✅ Sent as file.")
    else:
        await query.edit_message_text(f"❌ Failed: {result.get('error', 'unknown')}")

async def change_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = query.data.replace('changequality_', '')
    keyboard = [
        [
            InlineKeyboardButton("🔽 Low", callback_data=f"quality_low_{url}"),
            InlineKeyboardButton("🟡 Medium", callback_data=f"quality_medium_{url}"),
            InlineKeyboardButton("🔼 High", callback_data=f"quality_high_{url}")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    await query.edit_message_caption(
        caption="🎯 *Select new quality:*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def redownload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split('_', 2)
    if len(parts) < 3:
        await query.edit_message_caption("❌ Invalid request.")
        return
    quality = parts[1]
    url = parts[2]
    await query.edit_message_caption(f"⏳ Re-downloading in *{quality.upper()}*...", parse_mode='Markdown')
    result = fetch_media(url, quality)
    if result.get('success'):
        video_url = result.get('video_url')
        await query.message.reply_video(video=video_url, caption="📥 Re-downloaded")
        await query.edit_message_caption("✅ Done.")
    else:
        await query.edit_message_caption(f"❌ Error: {result.get('error', 'unknown')}")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = query.data.replace('info_', '')
    result = fetch_media(url, 'high')
    if result.get('success'):
        info_text = (
            f"📋 *Media Info*\n\n"
            f"👤 User: {result.get('username', 'N/A')}\n"
            f"📝 Caption: {result.get('caption', 'None')[:100]}\n"
            f"📊 Media Count: {result.get('media_count', 1)}\n"
            f"🖼 Thumbnail: [Link]({result.get('thumbnail', '#')})"
        )
        await query.edit_message_caption(caption=info_text, parse_mode='Markdown')
    else:
        await query.edit_message_caption("❌ Could not fetch info.")

async def developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msg = f"👨‍💻 *Developer*\n\nUsername: @{DEVELOPER_USERNAME}\n\nBuilt with ❤️ for KOHINOOR"
    await query.edit_message_caption(caption=msg, parse_mode='Markdown')

# ---------- MAIN ----------
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(CommandHandler('about', about))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(quality_callback, pattern=r'^quality_'))
    app.add_handler(CallbackQueryHandler(change_quality, pattern=r'^changequality_'))
    app.add_handler(CallbackQueryHandler(redownload, pattern=r'^redownload_'))
    app.add_handler(CallbackQueryHandler(info, pattern=r'^info_'))
    app.add_handler(CallbackQueryHandler(developer, pattern=r'^developer$'))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.edit_message_text("❌ Cancelled."), pattern=r'^cancel$'))
    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
