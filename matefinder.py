import telebot
from telebot import types

import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

users = {}
profiles = {}
likes = {}
active_chats = {}
admin_ids = [6535216093]  # Replace with your Telegram user ID

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    # If user already has profile, show welcome
    if user_id in profiles:
        bot.send_message(user_id, "👋 Welcome back! Use /find to search for matches.")
        return

    # If user already in process, skip intro
    if user_id in users:
        bot.send_message(user_id, "⚠️ You're already creating a profile. Continue with your details.")
        return

    # New user: show channel join (optional)
    markup = types.InlineKeyboardMarkup()
    join_button = types.InlineKeyboardButton(
        "🔔 Join our channel (optional)", url="https://t.me/MateFinderUpdates"  # replace with your actual channel
    )
    markup.add(join_button)

    bot.send_message(
        user_id,
        "📢 To stay updated, you can join our channel below (optional):",
        reply_markup=markup
    )

    # Start profile setup
    users[user_id] = {'step': 'name'}
    bot.send_message(user_id, "👤 Let's create your profile.\nWhat's your name?")
# Handle profile creation steps (text only)
@bot.message_handler(func=lambda msg: msg.from_user.id in users and msg.content_type == 'text')
def handle_profile_steps(message):
    user_id = message.from_user.id
    step = users[user_id]['step']
    text = message.text

    if step == 'name':
        users[user_id]['name'] = text
        users[user_id]['step'] = 'age'
        bot.send_message(user_id, "📅 Enter your age:")

    elif step == 'age':
        if not text.isdigit():
            bot.send_message(user_id, "⚠️ Please enter a valid age.")
            return
        users[user_id]['age'] = text
        users[user_id]['step'] = 'gender'
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add("Male", "Female", "Other")
        bot.send_message(user_id, "🚻 Select your gender:", reply_markup=markup)

    elif step == 'gender':
        users[user_id]['gender'] = text
        users[user_id]['step'] = 'place'
        bot.send_message(user_id, "📍 Where are you from?")

    elif step == 'place':
        users[user_id]['place'] = text
        users[user_id]['step'] = 'bio'
        bot.send_message(user_id, "📝 Write a short bio about yourself:")

    elif step == 'bio':
        users[user_id]['bio'] = text
        users[user_id]['step'] = 'photo'
        markup = types.ReplyKeyboardRemove()
        bot.send_message(user_id, "📸 Now send your photo:", reply_markup=markup)

# Handle photo uploads during profile creation
@bot.message_handler(content_types=['photo'])
def handle_photo_upload(message):
    user_id = message.from_user.id
    if user_id in users and users[user_id].get('step') == 'photo':
        users[user_id]['photo'] = message.photo[-1].file_id
        profiles[user_id] = users[user_id]
        users.pop(user_id)
        bot.send_message(user_id, "✅ Profile created successfully!")
    elif user_id in active_chats:
        partner = active_chats[user_id]
        bot.send_photo(partner, message.photo[-1].file_id)

# Show profile
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    profile = profiles.get(user_id)
    if profile:
        caption = f"👤 Name: {profile['name']}\n📅 Age: {profile['age']}\n🚻 Gender: {profile['gender']}\n📍 Place: {profile['place']}\n📝 Bio: {profile['bio']}"
        bot.send_photo(user_id, profile['photo'], caption=caption)
    else:
        bot.send_message(user_id, "⚠️ You don't have a profile yet. Use /start to create one.")

# Edit profile
@bot.message_handler(commands=['edit'])
def edit_profile(message):
    user_id = message.from_user.id
    users[user_id] = {'step': 'name'}
    bot.send_message(user_id, "🛠 Let's update your profile.\nWhat's your name?")

# Find match
@bot.message_handler(commands=['find'])
def find_match(message):
    @bot.callback_query_handler(func=lambda call: call.data == "next_profile")
def handle_next(call):
    find_match(call.message)
    user_id = message.from_user.id

    if user_id not in profiles:
        bot.send_message(user_id, "⚠️ Please complete your profile first with /start.")
        return

    liked = likes.get(user_id, [])
    skipped = dislikes.get(user_id, [])
    shown = set(liked + skipped)

    for uid, profile in profiles.items():
        if uid != user_id and uid not in shown:
            caption = (
                f"👤 Name: {profile['name']}\n"
                f"📅 Age: {profile['age']}\n"
                f"🚻 Gender: {profile['gender']}\n"
                f"📍 Place: {profile['place']}\n"
                f"📝 Bio: {profile['bio']}"
            )

            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("❤️ Like", callback_data=f"like_{uid}"),
                types.InlineKeyboardButton("❌ Skip", callback_data=f"dislike_{uid}")
            )
            markup.row(
                types.InlineKeyboardButton("➡️ Next", callback_data="next_profile")
            )

            bot.send_photo(user_id, profile['photo'], caption=caption, reply_markup=markup)
            return

    bot.send_message(user_id, "🔍 No more profiles to show right now.")

# Handle like/dislike
@bot.callback_query_handler(func=lambda call: call.data.startswith("like_") or call.data.startswith("dislike_"))
def handle_like_dislike(call):
    user_id = call.from_user.id
    target_id = int(call.data.split('_')[1])

    if call.data.startswith("like_"):
        likes.setdefault(user_id, []).append(target_id)

        if user_id in likes.get(target_id, []):
            bot.send_message(user_id, "🎉 It's a match! Use /chat to start talking.")
            bot.send_message(target_id, "🎉 It's a match! Use /chat to start talking.")
            active_chats[user_id] = target_id
            active_chats[target_id] = user_id
        else:
            bot.send_message(user_id, "👍 Liked!")

    elif call.data.startswith("dislike_"):
        dislikes.setdefault(user_id, []).append(target_id)
        bot.send_message(user_id, "👎 Skipped.")

    # ✅ Show next profile automatically
    find_match(call.message)

# Start chat
@bot.message_handler(commands=['chat'])
def start_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        bot.send_message(user_id, "💬 Send messages now. Use /stop to end chat.")
    else:
        bot.send_message(user_id, "❗ You are not matched with anyone yet.")

# Stop chat
@bot.message_handler(commands=['stop'])
def stop_chat(message):
    user_id = message.from_user.id
    partner = active_chats.get(user_id)
    if partner:
        bot.send_message(partner, "🔕 Chat ended by the other user.")
        active_chats.pop(partner, None)
        active_chats.pop(user_id, None)
    bot.send_message(user_id, "❌ Chat ended.")

# Forward messages between matched users
@bot.message_handler(func=lambda msg: msg.from_user.id in active_chats)
def forward_chat(msg):
    partner = active_chats.get(msg.from_user.id)
    if partner:
        if msg.content_type == 'text':
            bot.send_message(partner, f"🗣 {msg.text}")
        elif msg.content_type == 'photo':
            bot.send_photo(partner, msg.photo[-1].file_id)
        else:
            bot.send_message(msg.chat.id, "❌ Only text or photo allowed.")

# Admin panel
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id in admin_ids:
        total_users = len(profiles)
        bot.send_message(message.chat.id, f"👥 Total users: {total_users}")
    else:
        bot.send_message(message.chat.id, "🚫 You are not authorized.")

# Broadcast
@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id not in admin_ids:
        return
    parts = message.text.split(' ', 1)
    if len(parts) == 2:
        for uid in profiles:
            try:
                bot.send_message(uid, f"📢 Admin Message:\n{parts[1]}")
            except:
                continue

# Help command
@bot.message_handler(commands=['help'])
def show_help(message):
    help_text = (
        "🤖 *MateFinder Bot Commands:*\n\n"
        "/start - Start interaction or create a new profile\n"
        "/profile - View your current profile\n"
        "/edit - Edit your profile\n"
        "/find - Browse potential matches\n"
        "/chat - Start chatting with a matched person\n"
        "/stop - Stop current chat\n"
        "/help - Show all commands\n"
        "/admin - Admin panel\n"
        "/cancel - Cancel any current operation (profile/chat)\n"
        "/broadcast <message> - Send message to all users (admin only)"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")
# Cancel command
@bot.message_handler(commands=['cancel'])
def cancel_all(message):
    user_id = message.from_user.id

    # Cancel profile creation
    if user_id in users:
        users.pop(user_id)
    
    # Cancel active chat
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id)
        if partner_id in active_chats:
            active_chats.pop(partner_id)
            bot.send_message(partner_id, "⚠️ The other user has cancelled the chat.")

    # Confirm to user
    bot.send_message(user_id, "❌ All operations cancelled.\nUse /start to begin again.")
# Start polling
bot.infinity_polling()
