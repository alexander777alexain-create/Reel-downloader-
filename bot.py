import os
import logging
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_URL = os.environ.get('API_URL')
DEVELOPER_USERNAME = os.environ.get('DEVELOPER_USERNAME', 'll_VIPIN_ll')
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME')
ADMIN_ID = os.environ.get('ADMIN_ID')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")
if not API_URL:
    raise ValueError("API_URL environment variable not set")
if not CHANNEL_USERNAME:
    raise ValueError("CHANNEL_USERNAME environment variable not set")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID environment variable not set")

ADMIN_ID = int(ADMIN_ID)
USERS_FILE = 'users.txt'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- USER STORAGE ----------
def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return set(line.strip() for line in f if line.strip())
    except:
        pass
    return set()

def save_user(user_id):
    users = load_users()
    if str(user_id) not in users:
        with open(USERS_FILE, 'a') as f:
            f.write(f"{user_id}\n")
        logger.info(f"New user saved: {user_id}")

# ---------- FORCE JOIN CHECK ----------
async def is_user_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=f"@{CHANNEL_USERNAME}",
            user_id=user_id
        )
        status = chat_member.status
        return status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.warning(f"Force join check failed: {e}")
        return False

async def send_join_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"🔒 *Please join our channel first!*\n\n"
        f"To use this bot, you need to join:\n"
        f"👉 @{CHANNEL_USERNAME}\n\n"
        f"After joining, click /start again."
    )
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")]
    ]
    await update.message.reply_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- HELPERS ----------
def extract_instagram_url(text):
    pattern = r'(https?://(?:www\.)?instagram\.com/(?:reel|p|tv|stories)/[a-zA-Z0-9_-]+(?:\?[^\s]*)?)'
    match = re.search(pattern, text)
    return match.group(1) if match else None

def fetch_media(url):
    try:
        resp = requests.get(API_URL, params={'url': url}, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return {'error': f'API returned {resp.status_code}'}
    except requests.Timeout:
        return {'error': '⏳ Timeout — try again'}
    except Exception as e:
        return {'error': str(e)}

def delete_webhook(token):
    try:
        url = f"https://api.telegram.org/bot{token}/deleteWebhook"
        requests.get(url, timeout=5)
    except:
        pass

# ---------- BROADCAST ----------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send message to all users (admin only) — supports reply"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    users = load_users()
    if not users:
        await update.message.reply_text("❌ No users found in database.")
        return
    
    reply_msg = update.message.reply_to_message
    
    if not reply_msg and not context.args:
        await update.message.reply_text(
            "📢 *Broadcast Usage:*\n\n"
            "1️⃣ Reply to any message with /broadcast\n"
            "2️⃣ Or use: /broadcast <message>\n\n"
            "Example: /broadcast Hello everyone!"
        )
        return
    
    progress_msg = await update.message.reply_text(f"⏳ Sending broadcast to {len(users)} users...")
    
    success_count = 0
    fail_count = 0
    
    for uid in users:
        try:
            if reply_msg:
                await reply_msg.forward(chat_id=int(uid))
            else:
                text = ' '.join(context.args)
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"📢 *Broadcast*\n\n{text}",
                    parse_mode='Markdown'
                )
            success_count += 1
        except Exception as e:
            fail_count += 1
            logger.warning(f"Broadcast failed to {uid}: {e}")
    
    await progress_msg.edit_text(
        f"✅ Broadcast complete!\n\n"
        f"✅ Sent: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"📊 Total: {len(users)}"
    )

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id)
    
    if not await is_user_member(update, context):
        await send_join_message(update, context)
        return

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🆕 *New User Started Bot*\n\n"
                 f"👤 User: {user.first_name} (@{user.username or 'No username'})\n"
                 f"🆔 ID: `{user.id}`\n"
                 f"📊 Total Users: {len(load_users())}"
        )
    except:
        pass

    msg = (
        f"👋 Hello {user.first_name}!\n\n"
        "Send me any Instagram link and I'll download it.\n\n"
        "📌 Supported: Reels, Posts, Carousels, Stories\n"
        "⚡ Direct best quality video"
    )
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        await send_join_message(update, context)
        return

    msg = (
        "📖 *How to use:*\n\n"
        "1️⃣ Send Instagram link\n"
        "2️⃣ Bot fetches and sends video\n\n"
        "*Commands:*\n"
        "/start — Welcome\n"
        "/help — This message\n"
        "/about — Bot info"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        await send_join_message(update, context)
        return

    msg = (
        "🤖 *Instagram Downloader Bot*\n\n"
        "Built with ❤️ for our LOVELY PEOPLE.\n\n"
        f"👨‍💻 Developer: @{DEVELOPER_USERNAME}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only.")
        return
    
    users = load_users()
    await update.message.reply_text(
        f"📊 *Bot Stats*\n\n"
        f"👥 Total Users: {len(users)}\n"
        f"🤖 Bot Status: Online"
    )

# ---------- MESSAGE HANDLER ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        await send_join_message(update, context)
        return

    text = update.message.text
    url = extract_instagram_url(text)
    if not url:
        await update.message.reply_text("❌ No Instagram link found.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)

    result = fetch_media(url)

    if result.get('success'):
        video_url = result.get('video_url')
        username = result.get('username', 'Unknown')
        caption_text = result.get('caption', '')[:200]

        caption = f"🎬 *{username}*\n\n{caption_text}"

        context.user_data['last_url'] = url

        keyboard = [
            [
                InlineKeyboardButton("📥 Download", url=video_url),
                InlineKeyboardButton("🔁 Re-download", callback_data=f"redownload_{url}")
            ],
            [
                InlineKeyboardButton("ℹ️ Info", callback_data=f"info_{url}"),
                InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{DEVELOPER_USERNAME}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await update.message.reply_video(
                video=video_url,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=reply_markup,
                supports_streaming=True
            )
        except Exception:
            await update.message.reply_document(
                document=video_url,
                caption=f"📁 {username}\n\n{caption_text}",
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(f"❌ Failed: {result.get('error', 'unknown')}")

# ---------- CALLBACKS ----------
async def redownload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        await update.callback_query.answer("Please join the channel first!")
        await update.callback_query.message.reply_text(
            f"🔒 Please join @{CHANNEL_USERNAME} first!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")]
            ])
        )
        return

    query = update.callback_query
    await query.answer()
    url = query.data.replace('redownload_', '')

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
    await query.edit_message_text("⏳ Re-downloading...")

    result = fetch_media(url)
    if result.get('success'):
        video_url = result.get('video_url')
        username = result.get('username', 'Unknown')
        caption_text = result.get('caption', '')[:200]
        caption = f"🎬 *{username}*\n\n{caption_text}"

        keyboard = [
            [
                InlineKeyboardButton("📥 Download", url=video_url),
                InlineKeyboardButton("🔁 Re-download", callback_data=f"redownload_{url}")
            ],
            [
                InlineKeyboardButton("ℹ️ Info", callback_data=f"info_{url}"),
                InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{DEVELOPER_USERNAME}")
            ]
        ]
        try:
            await query.message.reply_video(
                video=video_url,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard),
                supports_streaming=True
            )
            await query.edit_message_text("✅ Re-downloaded!")
        except Exception:
            await query.message.reply_document(
                document=video_url,
                caption=f"📁 {username}\n\n{caption_text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await query.edit_message_text("✅ Re-downloaded as file.")
    else:
        await query.edit_message_text(f"❌ Failed: {result.get('error', 'unknown')}")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_member(update, context):
        await update.callback_query.answer("Please join the channel first!")
        await update.callback_query.message.reply_text(
            f"🔒 Please join @{CHANNEL_USERNAME} first!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")]
            ])
        )
        return

    query = update.callback_query
    await query.answer()
    url = query.data.replace('info_', '')
    result = fetch_media(url)
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

# ---------- MAIN ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    delete_webhook(BOT_TOKEN)

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(CommandHandler('about', about))
    app.add_handler(CommandHandler('broadcast', broadcast))
    app.add_handler(CommandHandler('stats', stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(redownload, pattern=r'^redownload_'))
    app.add_handler(CallbackQueryHandler(info, pattern=r'^info_'))
    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
