import logging
import random
from datetime import datetime
from tinydb import TinyDB, Query
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ConversationHandler
)

# Initialize
logging.basicConfig(level=logging.INFO)
db = TinyDB("matefinder_db.json")
users_table = db.table("users")
likes_table = db.table("likes")
skips_table = db.table("skips")
waiting_table = db.table("waiting")
muted_table = db.table("muted")
banned_table = db.table("banned")
chat_pairs = {}
random_waiting = []

# States
PROFILE_NAME, PROFILE_AGE, PROFILE_GENDER, PROFILE_PHOTO, PROFILE_PLACE, PROFILE_BIO = range(6)
FINDING, COMMENTING, MATCH_CHAT, RANDOM_CHAT = range(6, 10)

# Utils
def get_user(user_id):
    return users_table.get(Query().user_id == user_id)

def save_user(data):
    users_table.upsert(data, Query().user_id == data['user_id'])

def add_like(liker, liked):
    likes_table.insert({'from': liker, 'to': liked})

def add_skip(skipper, skipped):
    skips_table.insert({'from': skipper, 'to': skipped})

def get_mutual_likes(user_id):
    sent = likes_table.search(Query().from_ == user_id)
    received = likes_table.search(Query().to == user_id)
    sent_ids = {x['to'] for x in sent}
    received_ids = {x['from'] for x in received}
    return list(sent_ids & received_ids)

def is_banned(user_id):
    return banned_table.contains(Query().user_id == user_id)

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("⛔ You are banned from using this bot.")
        return
    keyboard = [
        [InlineKeyboardButton("Join Channel", url="https://t.me/MateFinderUpdatesl")],
        [InlineKeyboardButton("Skip", callback_data="skip_channel")]
    ]
    await update.message.reply_text("Welcome to MateFinder! Join our channel or skip.",
                                    reply_markup=InlineKeyboardMarkup(keyboard))

async def skip_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("👋 Welcome to MateFinder! Let's create your profile. What's your name?")
    return PROFILE_NAME

# Profile Creation Handlers
async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Your age?")
    return PROFILE_AGE

async def profile_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    await update.message.reply_text("Your gender? (Male/Female/Other)")
    return PROFILE_GENDER

async def profile_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    await update.message.reply_text("Send your profile photo.")
    return PROFILE_PHOTO

async def profile_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['photo'] = update.message.photo[-1].file_id
    await update.message.reply_text("Optional: Your place (or type /skip)")
    return PROFILE_PLACE

async def profile_place(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['place'] = update.message.text
    await update.message.reply_text("Optional: Your bio (or type /skip)")
    return PROFILE_BIO

async def skip_optional(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await save_profile(update, context)

async def profile_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bio'] = update.message.text
    return await save_profile(update, context)

async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = {
        'user_id': user.id,
        'name': context.user_data['name'],
        'age': context.user_data['age'],
        'gender': context.user_data['gender'],
        'photo': context.user_data['photo'],
        'place': context.user_data.get('place', ''),
        'bio': context.user_data.get('bio', ''),
        'joined': str(datetime.now())
    }
    save_user(data)
    await update.message.reply_text("✅ Profile saved! Use /find to browse.")
    return ConversationHandler.END

# Chat Commands
async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💞 Chat with Match", callback_data="match_chat")],
        [InlineKeyboardButton("🔀 Random Chat", callback_data="random_chat")]
    ]
    await update.message.reply_text("Choose a chat mode:", reply_markup=InlineKeyboardMarkup(keyboard))

async def chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "match_chat":
        mutuals = get_mutual_likes(user_id)
        random.shuffle(mutuals)
        for match in mutuals:
            if match not in chat_pairs.values():
                chat_pairs[user_id] = match
                chat_pairs[match] = user_id
                await context.bot.send_message(match, "💞 You're now in match chat!")
                await query.message.reply_text("✅ Connected to a mutual like. Start chatting!")
                return MATCH_CHAT
        await query.message.reply_text("No available mutual likes at the moment.")

    elif query.data == "random_chat":
        if random_waiting and random_waiting[0] != user_id:
            partner = random_waiting.pop(0)
            chat_pairs[user_id] = partner
            chat_pairs[partner] = user_id
            await context.bot.send_message(partner, "🔀 You've been paired in random chat!")
            await query.message.reply_text("✅ Connected to random user. Start chatting!")
        else:
            random_waiting.append(user_id)
            await query.message.reply_text("⌛ Waiting for a partner...")

# Stop Chat
async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in chat_pairs:
        partner = chat_pairs.pop(user_id)
        chat_pairs.pop(partner, None)
        await context.bot.send_message(partner, "⚠️ Chat ended by your partner.")
        await update.message.reply_text("✅ You left the chat.")
    else:
        await update.message.reply_text("❌ You're not in any chat.")

# Relay Messages
async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in chat_pairs:
        partner_id = chat_pairs[user_id]
        if update.message.text:
            await context.bot.send_message(partner_id, update.message.text)
        elif update.message.photo:
            await context.bot.send_photo(partner_id, update.message.photo[-1].file_id)

# Entry Point
if __name__ == '__main__':
    from telegram.ext import ApplicationBuilder

    app = ApplicationBuilder().token("BOT_TOKEN").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(skip_channel, pattern="skip_channel"))
    app.add_handler(CommandHandler("chat", chat_command))
    app.add_handler(CallbackQueryHandler(chat_callback, pattern="^(match_chat|random_chat)$"))
    app.add_handler(CommandHandler("stop", stop_chat))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, relay))

    # Profile Conversation
    profile_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(skip_channel, pattern="skip_channel")],
        states={
            PROFILE_NAME: [MessageHandler(filters.TEXT, profile_name)],
            PROFILE_AGE: [MessageHandler(filters.TEXT, profile_age)],
            PROFILE_GENDER: [MessageHandler(filters.TEXT, profile_gender)],
            PROFILE_PHOTO: [MessageHandler(filters.PHOTO, profile_photo)],
            PROFILE_PLACE: [MessageHandler(filters.TEXT, profile_place), CommandHandler("skip", skip_optional)],
            PROFILE_BIO: [MessageHandler(filters.TEXT, profile_bio), CommandHandler("skip", skip_optional)]
        },
        fallbacks=[CommandHandler("cancel", skip_optional)]
    )
    app.add_handler(profile_conv)

    app.run_polling()
