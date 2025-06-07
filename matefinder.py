import telebot
from telebot import types
from tinydb import TinyDB, Query

# --- Config ---
BOT_TOKEN = 'BOT_TOKEN'  # Replace when deploying
bot = telebot.TeleBot(BOT_TOKEN)
db = TinyDB("users.json")
User = Query()
states = {}

# --- Start & Profile Creation ---
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = msg.from_user.id
    if db.search(User.id == user_id):
        bot.send_message(user_id, "Welcome back! Use /find to start finding matches or /profile to view your profile.")
    else:
        states[user_id] = {'step': 'name'}
        bot.send_message(user_id, "Welcome to MateFinder!\nLet's set up your profile.\n\nWhat's your name?")

@bot.message_handler(func=lambda msg: msg.from_user.id in states)
def profile_setup(msg):
    user_id = msg.from_user.id
    text = msg.text
    step = states[user_id]['step']

    if step == 'name':
        states[user_id]['name'] = text
        states[user_id]['step'] = 'age'
        bot.send_message(user_id, "Your age?")
    elif step == 'age':
        if not text.isdigit():
            bot.send_message(user_id, "Please enter a valid age.")
            return
        states[user_id]['age'] = int(text)
        states[user_id]['step'] = 'gender'
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        markup.add('Male', 'Female', 'Other')
        bot.send_message(user_id, "Your gender?", reply_markup=markup)
    elif step == 'gender':
        states[user_id]['gender'] = text
        states[user_id]['step'] = 'photo'
        bot.send_message(user_id, "Please send your photo.", reply_markup=types.ReplyKeyboardRemove())
    elif step == 'place':
        states[user_id]['place'] = text
        states[user_id]['step'] = 'bio'
        bot.send_message(user_id, "Write a short bio (or skip).")
    elif step == 'bio':
        states[user_id]['bio'] = text
        save_profile(user_id)
    else:
        bot.send_message(user_id, "Please follow the profile setup process.")

@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    user_id = msg.from_user.id
    if user_id in states and states[user_id]['step'] == 'photo':
        photo_id = msg.photo[-1].file_id
        states[user_id]['photo'] = photo_id
        states[user_id]['step'] = 'place'
        bot.send_message(user_id, "Where are you from?")
    else:
        pass  # Ignore random photos

def save_profile(user_id):
    data = states[user_id]
    profile = {
        'id': user_id,
        'name': data.get('name'),
        'age': data.get('age'),
        'gender': data.get('gender'),
        'photo': data.get('photo'),
        'place': data.get('place', ''),
        'bio': data.get('bio', ''),
        'likes': [],
        'liked_by': [],
        'comments': []
    }
    db.insert(profile)
    del states[user_id]
    bot.send_message(user_id, "✅ Profile created! Use /find to view profiles.")

# --- View Profile ---
@bot.message_handler(commands=['profile'])
def view_profile(msg):
    user_id = msg.from_user.id
    user = get_user(user_id)
    if user:
        text = f"👤 Name: {user['name']}\n🎂 Age: {user['age']}\n⚧ Gender: {user['gender']}\n📍 Place: {user.get('place', '')}\n📝 Bio: {user.get('bio', '')}\n❤️ Likes: {len(user['liked_by'])}"
        bot.send_photo(user_id, user['photo'], caption=text)
    else:
        bot.send_message(user_id, "You haven't created a profile. Use /start.")

# --- Edit Profile ---
@bot.message_handler(commands=['edit'])
def edit_profile(msg):
    user_id = msg.from_user.id
    user = get_user(user_id)
    if not user:
        bot.send_message(user_id, "Profile not found. Use /start.")
        return
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("Name", "Age", "Gender", "Place", "Bio", "Photo")
    bot.send_message(user_id, "What do you want to edit?", reply_markup=markup)
    states[user_id] = {'step': 'edit_field'}

@bot.message_handler(func=lambda msg: msg.from_user.id in states and states[msg.from_user.id]['step'] == 'edit_field')
def handle_edit_field(msg):
    user_id = msg.from_user.id
    field = msg.text.lower()
    if field in ['name', 'age', 'gender', 'place', 'bio', 'photo']:
        states[user_id]['field'] = field
        states[user_id]['step'] = 'edit_value'
        if field == 'photo':
            bot.send_message(user_id, "Send new photo:")
        else:
            bot.send_message(user_id, f"Enter new {field}:")
    else:
        bot.send_message(user_id, "Invalid choice. Use /edit again.")
        del states[user_id]

@bot.message_handler(func=lambda msg: msg.from_user.id in states and states[msg.from_user.id]['step'] == 'edit_value')
def save_edit(msg):
    user_id = msg.from_user.id
    field = states[user_id]['field']
    if field == 'photo':
        bot.send_message(user_id, "Please send a photo.")
        return
    db.update({field: msg.text}, User.id == user_id)
    bot.send_message(user_id, f"{field.capitalize()} updated.")
    del states[user_id]

@bot.message_handler(content_types=['photo'])
def update_photo(msg):
    user_id = msg.from_user.id
    if user_id in states and states[user_id].get('field') == 'photo':
        photo_id = msg.photo[-1].file_id
        db.update({'photo': photo_id}, User.id == user_id)
        bot.send_message(user_id, "Photo updated!")
        del states[user_id]

# --- Cancel Profile Setup ---
@bot.message_handler(commands=['cancel'])
def cancel(msg):
    user_id = msg.from_user.id
    if user_id in states:
        del states[user_id]
        bot.send_message(user_id, "Profile setup canceled.")
    else:
        bot.send_message(user_id, "Nothing to cancel.")

# --- Help ---
@bot.message_handler(commands=['help'])
def help_command(msg):
    bot.send_message(msg.chat.id, """
🤖 MateFinder Commands:
/start - Create your profile
/find - Browse profiles
/profile - View your profile
/edit - Edit your profile
/likehistory - Who you liked
/help - Show this message
/cancel - Cancel current action
""")

# --- Like, Comment, Find ---
@bot.message_handler(commands=['find'])
def find(msg):
    user_id = msg.from_user.id
    current_user = get_user(user_id)
    if not current_user:
        bot.send_message(user_id, "Create a profile first with /start.")
        return
    others = db.search((User.id != user_id) & (~User.id.one_of(current_user['likes'])))
    if not others:
        bot.send_message(user_id, "No more profiles. Try again later.")
        return
    profile = others[0]
    text = f"👤 {profile['name']}, {profile['age']}, {profile['gender']}\n📍 {profile.get('place','')}\n📝 {profile.get('bio','')}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❤️ Like", callback_data=f"like:{profile['id']}"),
               types.InlineKeyboardButton("💬 Comment", callback_data=f"comment:{profile['id']}"),
               types.InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{profile['id']}"))
    bot.send_photo(user_id, profile['photo'], caption=text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = call.from_user.id
    data = call.data
    if data.startswith('like:'):
        liked_id = int(data.split(":")[1])
        db.update(add_to_list('likes', liked_id), User.id == user_id)
        db.update(add_to_list('liked_by', user_id), User.id == liked_id)
        bot.answer_callback_query(call.id, "Liked!")
        check_match(user_id, liked_id)
        find(call.message)
    elif data.startswith('skip:'):
        find(call.message)
    elif data.startswith('comment:'):
        states[user_id] = {'step': 'comment', 'target': int(data.split(":")[1])}
        bot.send_message(user_id, "Type your comment:")

@bot.message_handler(func=lambda msg: msg.from_user.id in states and states[msg.from_user.id]['step'] == 'comment')
def handle_comment(msg):
    user_id = msg.from_user.id
    target_id = states[user_id]['target']
    comment_text = msg.text
    comment = f"{user_id}: {comment_text}"
    db.update(add_to_list('comments', comment), User.id == target_id)
    bot.send_message(user_id, "💬 Comment added.")
    del states[user_id]
    find(msg)

# --- Like History ---
@bot.message_handler(commands=['likehistory'])
def likehistory(msg):
    user_id = msg.from_user.id
    user = get_user(user_id)
    if not user or not user['likes']:
        bot.send_message(user_id, "No likes yet.")
        return
    for uid in user['likes']:
        liked = get_user(uid)
        if liked:
            text = f"{liked['name']}, {liked['age']}, {liked['gender']}"
            bot.send_photo(user_id, liked['photo'], caption=text)

# --- Helper Functions ---
def get_user(uid):
    u = db.search(User.id == uid)
    return u[0] if u else None

def add_to_list(field, val):
    return lambda doc: doc[field] + [val] if val not in doc[field] else doc[field]

def check_match(uid1, uid2):
    u1 = get_user(uid1)
    if uid2 in u1['liked_by']:
        bot.send_message(uid1, "🎉 It's a match! Start chatting.")
        bot.send_message(uid2, "🎉 It's a match! Start chatting.")

# --- Run Bot ---
bot.infinity_polling()
