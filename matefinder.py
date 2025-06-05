import telebot
from telebot import types

bot = telebot.TeleBot("bot_token")

users = {}
profiles = {}
likes = {}
active_chats = {}
admin_ids = [6535216093]  # Replace with your Telegram user ID

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if user_id in profiles:
        bot.send_message(user_id, "👤 You already have a profile. Use /edit to update it.")
        return

    users[user_id] = {'step': 'name'}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔔 Join our channel (optional)", url="https://t.me/MateFinderUpdates"))
    bot.send_message(user_id, "👋 Welcome to MateFinder!\nLet's create your profile.\nWhat’s your name?", reply_markup=markup)

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
    user_id = message.from_user.id
    if user_id not in profiles:
        bot.send_message(user_id, "⚠️ Please complete your profile with /start first.")
        return

    for uid, profile in profiles.items():
        if uid != user_id and uid not in likes.get(user_id, []):
            caption = f"👤 Name: {profile['name']}\n📅 Age: {profile['age']}\n🚻 Gender: {profile['gender']}\n📍 Place: {profile['place']}\n📝 Bio: {profile['bio']}"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("❤️ Like", callback_data=f"like_{uid}"),
                types.InlineKeyboardButton("❌ Skip", callback_data=f"dislike_{uid}")
            )
            bot.send_photo(user_id, profile['photo'], caption=caption, reply_markup=markup)
            return

    bot.send_message(user_id, "🔍 No more profiles to show right now. Try again later.")

# Handle like/dislike
@bot.callback_query_handler(func=lambda call: call.data.startswith("like_") or call.data.startswith("dislike_"))
def handle_like_dislike(call):
    user_id = call.from_user.id
    target_id = int(call.data.split('_')[1])

    if call.data.startswith("like_"):
        likes.setdefault(user_id, []).append(target_id)
        if user_id in likes.get(target_id, []):
            active_chats[user_id] = target_id
            active_chats[target_id] = user_id
            bot.send_message(user_id, "🎉 It's a match! Start chatting with /chat")
            bot.send_message(target_id, "🎉 It's a match! Start chatting with /chat")
        else:
            bot.send_message(user_id, "👍 You liked the profile.")
    else:
        likes.setdefault(user_id, []).append(target_id)
        bot.send_message(user_id, "⏩ Skipped.")

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
        "/broadcast <message> - Send message to all users (admin only)"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

# Start polling
bot.infinity_polling()
