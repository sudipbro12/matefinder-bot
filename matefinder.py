import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import random

# Your bot token here
TOKEN = "YOUR_BOT_TOKEN"
bot = telebot.TeleBot(TOKEN)

users = {}  # user_id: profile dict
likes = {}  # user_id: set of liked user_ids
skips = {}  # user_id: set of skipped user_ids
active_chats = {}  # user_id: partner_id
random_queue = []
admins = [123456789]  # replace with your Telegram user ID

# --- States ---
user_states = {}
STATE_NAME, STATE_AGE, STATE_GENDER, STATE_PHOTO = range(4)

# --- Utilities ---
def get_profile_text(profile):
    text = f"👤 {profile['name']}, {profile['age']}, {profile['gender']}"
    return text

def reset_chat(user_id):
    partner = active_chats.pop(user_id, None)
    if partner:
        active_chats.pop(partner, None)
        bot.send_message(partner, "❌ Chat ended by partner.")

# --- Start ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 Join Channel", url="https://t.me/MateFinderUpdates"))
    markup.add(InlineKeyboardButton("✅ Skip", callback_data="skip_channel"))
    bot.send_message(user_id, "👋 Welcome to MateFinder! Please join our update channel:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "skip_channel")
def skip_channel(call):
    user_id = call.from_user.id
    bot.send_message(user_id, "Let’s create your profile.\nWhat is your name?")
    user_states[user_id] = STATE_NAME

# --- Profile Creation ---
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == STATE_NAME)
def get_name(message):
    user_id = message.from_user.id
    users[user_id] = {"id": user_id, "name": message.text}
    bot.send_message(user_id, "Your age?")
    user_states[user_id] = STATE_AGE

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == STATE_AGE)
def get_age(message):
    user_id = message.from_user.id
    users[user_id]["age"] = message.text
    bot.send_message(user_id, "Your gender (Male/Female/Other)?")
    user_states[user_id] = STATE_GENDER

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == STATE_GENDER)
def get_gender(message):
    user_id = message.from_user.id
    users[user_id]["gender"] = message.text
    bot.send_message(user_id, "Please send your profile photo.")
    user_states[user_id] = STATE_PHOTO

@bot.message_handler(content_types=['photo'], func=lambda m: user_states.get(m.from_user.id) == STATE_PHOTO)
def get_photo(message):
    user_id = message.from_user.id
    users[user_id]["photo"] = message.photo[-1].file_id
    likes[user_id] = set()
    skips[user_id] = set()
    user_states.pop(user_id)
    bot.send_message(user_id, "✅ Profile saved! Use /find to start finding matches.")

# --- Find Matches ---
@bot.message_handler(commands=['find'])
def find_profile(message):
    user_id = message.from_user.id
    if user_id not in users:
        bot.send_message(user_id, "⚠️ Please create a profile first using /start.")
        return

    available = [uid for uid in users if uid != user_id and uid not in likes[user_id] and uid not in skips[user_id]]
    if not available:
        bot.send_message(user_id, "🔁 No new profiles now. Try again later.")
        return

    target_id = random.choice(available)
    target = users[target_id]
    caption = get_profile_text(target)

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("👍 Like", callback_data=f"like_{target_id}"),
        InlineKeyboardButton("👎 Skip", callback_data=f"skip_{target_id}")
    )
    bot.send_photo(user_id, photo=target["photo"], caption=caption, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("like_"))
def handle_like(call):
    user_id = call.from_user.id
    target_id = int(call.data.split("_")[1])
    likes[user_id].add(target_id)

    if user_id in likes.get(target_id, set()):
        # Match!
        active_chats[user_id] = target_id
        active_chats[target_id] = user_id
        bot.send_message(user_id, "💞 You matched! Say hi!")
        bot.send_message(target_id, "💞 You matched! Say hi!")
    else:
        bot.send_message(user_id, "👍 Liked. Use /find to see more.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("skip_"))
def handle_skip(call):
    user_id = call.from_user.id
    target_id = int(call.data.split("_")[1])
    skips[user_id].add(target_id)
    bot.send_message(user_id, "⏭️ Skipped. Use /find to continue.")

# --- Like History ---
@bot.message_handler(commands=['likehistory'])
def likehistory(message):
    user_id = message.from_user.id
    liked_ids = likes.get(user_id, set())
    if not liked_ids:
        bot.send_message(user_id, "📭 You haven't liked anyone yet.")
    else:
        lines = [f"❤️ {users[uid]['name']} ({users[uid]['age']})" for uid in liked_ids if uid in users]
        bot.send_message(user_id, "\n".join(lines))

# --- Chat System ---
@bot.message_handler(commands=['chat'])
def random_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        bot.send_message(user_id, "⚠️ You're already in a chat.")
        return

    for partner in random_queue:
        if partner != user_id:
            random_queue.remove(partner)
            active_chats[user_id] = partner
            active_chats[partner] = user_id
            bot.send_message(user_id, "🔀 Partner found! Say hi!")
            bot.send_message(partner, "🔀 Partner found! Say hi!")
            return

    random_queue.append(user_id)
    bot.send_message(user_id, "⏳ Waiting for a random partner...")

@bot.message_handler(commands=['stop'])
def stop_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        reset_chat(user_id)
        bot.send_message(user_id, "❌ Chat ended.")
    else:
        bot.send_message(user_id, "⚠️ You're not in a chat.")

@bot.message_handler(func=lambda m: m.from_user.id in active_chats)
def forward_chat(message):
    sender = message.from_user.id
    receiver = active_chats.get(sender)
    if not receiver:
        return

    if message.text:
        bot.send_message(receiver, f"💬 {message.text}")
    elif message.photo:
        bot.send_photo(receiver, message.photo[-1].file_id)
    elif message.sticker:
        bot.send_sticker(receiver, message.sticker.file_id)

# --- Admin Panel ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    if user_id not in admins:
        bot.send_message(user_id, "⛔ You are not an admin.")
        return

    total = len(users)
    bot.send_message(user_id, f"👥 Total Users: {total}")

# --- Run Bot ---
bot.polling()
