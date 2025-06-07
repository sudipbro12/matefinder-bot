import logging
import random
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Token (Replace with your real token before running)
TOKEN = "BOT_TOKEN"
CHANNEL_USERNAME = "@MateFinderUpdates"

# States
NAME, AGE, GENDER, PHOTO, PLACE, BIO = range(6)

# In-memory data
users = {}
likes = {}
skips = {}
matched_pairs = set()
random_chat_queue = []
active_chats = {}
banned_users = set()
muted_users = set()

# Utility
def get_user(user_id):
    return users.get(user_id)

def get_other_profiles(viewer_id):
    return [u for uid, u in users.items() if uid != viewer_id]

def end_chat(user_id):
    partner_id = active_chats.pop(user_id, None)
    if partner_id:
        active_chats.pop(partner_id, None)
    return partner_id

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in banned_users:
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return

    keyboard = [
        [InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
        [InlineKeyboardButton("✅ Skip", callback_data="skip_channel")]
    ]
    await update.message.reply_text(
        "👋 Welcome to MateFinder! Please join our update channel before continuing:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def skip_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Welcome to MateFinder! How are you?")
    await update.callback_query.message.reply_text("Let’s create your profile. What’s your name?")
    return NAME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Action cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Profile creation
async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        await update.message.reply_text("Please send your name as text.")
        return NAME
    context.user_data['name'] = update.message.text
    await update.message.reply_text("How old are you?")
    return AGE

async def age_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text or not update.message.text.isdigit():
        await update.message.reply_text("Please enter your age as a number.")
        return AGE
    context.user_data['age'] = int(update.message.text)
    await update.message.reply_text("Your gender (Male/Female/Other)?")
    return GENDER

async def gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        await update.message.reply_text("Please enter your gender (Male/Female/Other).")
        return GENDER
    context.user_data['gender'] = update.message.text
    await update.message.reply_text("Please send your profile photo.")
    return PHOTO

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Please send a photo to continue.")
        return PHOTO
    context.user_data['photo'] = update.message.photo[-1].file_id
    await update.message.reply_text("Where are you from? (Optional, type /skip to skip)")
    return PLACE

async def place_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['place'] = update.message.text if update.message.text else ""
    await update.message.reply_text("Write a short bio about yourself. (Optional, type /skip to skip)")
    return BIO

async def skip_place(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['place'] = ""
    await update.message.reply_text("Write a short bio about yourself. (Optional, type /skip to skip)")
    return BIO

async def bio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bio'] = update.message.text if update.message.text else ""
    return await save_profile(update, context)

async def skip_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bio'] = ""
    return await save_profile(update, context)

async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users[user_id] = {
        'id': user_id,
        'name': context.user_data['name'],
        'age': context.user_data['age'],
        'gender': context.user_data['gender'],
        'photo': context.user_data['photo'],
        'place': context.user_data.get('place', ''),
        'bio': context.user_data.get('bio', '')
    }
    likes[user_id] = set()
    skips[user_id] = set()
    await update.message.reply_text("✅ Profile created successfully! Use /find to start browsing.")
    return ConversationHandler.END

# Chat system
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💞 Match Chat", callback_data="match_chat")],
        [InlineKeyboardButton("🔀 Random Chat", callback_data="random_chat")]
    ]
    await update.message.reply_text("Choose a chat mode:", reply_markup=InlineKeyboardMarkup(keyboard))

async def match_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    partner_id = None
    for other_id, other_likes in likes.items():
        if user_id in other_likes and other_id in likes[user_id] and other_id not in active_chats:
            partner_id = other_id
            break

    if partner_id:
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id
        await context.bot.send_message(partner_id, "💞 You’ve matched! Start chatting.")
        await update.callback_query.message.reply_text("💞 You’ve matched! Start chatting.")
    else:
        await update.callback_query.message.reply_text("❗ No matches found yet. Like more profiles with /find.")

async def random_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    if user_id in random_chat_queue:
        await update.callback_query.message.reply_text("⏳ You are already in the queue. Please wait.")
        return

    for uid in random_chat_queue:
        if uid != user_id:
            partner_id = uid
            random_chat_queue.remove(uid)
            active_chats[user_id] = partner_id
            active_chats[partner_id] = user_id
            await context.bot.send_message(partner_id, "🔀 Partner found! Start chatting.")
            await update.callback_query.message.reply_text("🔀 Partner found! Start chatting.")
            return

    random_chat_queue.append(user_id)
    await update.callback_query.message.reply_text("⏳ Waiting for a random partner...")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    partner_id = active_chats.get(user_id)
    if partner_id:
        if update.message.text:
            await context.bot.send_message(partner_id, f"💬 {update.message.text}")
        elif update.message.photo:
            await context.bot.send_photo(partner_id, photo=update.message.photo[-1].file_id)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    partner_id = end_chat(user_id)
    if partner_id:
        await context.bot.send_message(partner_id, "❌ Your chat has ended.")
        await update.message.reply_text("❌ You ended the chat.")
    else:
        await update.message.reply_text("⚠️ You are not in a chat.")

# --- Main ---
def main():
    app = Application.builder().token(TOKEN).build()

    profile_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(skip_channel, pattern="^skip_channel$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age_handler)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender_handler)],
            PHOTO: [MessageHandler(filters.PHOTO, photo_handler)],
            PLACE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, place_handler),
                CommandHandler("skip", skip_place)
            ],
            BIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bio_handler),
                CommandHandler("skip", skip_bio)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile_conv)
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("chat", chat))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(match_chat, pattern="^match_chat$"))
    app.add_handler(CallbackQueryHandler(random_chat, pattern="^random_chat$"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, message_handler))

    app.run_polling()

if __name__ == '__main__':
    main()
