from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

waiting = []
chat_pairs = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid in chat_pairs:
        await update.message.reply_text("🗣️ You're already in a chat. Use /stop to end.")
        return

    if uid not in waiting:
        waiting.append(uid)
        await update.message.reply_text("🔍 Searching for a match...")

    if len(waiting) >= 2:
        user1 = waiting.pop(0)
        user2 = waiting.pop(0)
        chat_pairs[user1] = user2
        chat_pairs[user2] = user1

        await context.bot.send_message(user1, "💌 You're now chatting anonymously. Type /stop to end.")
        await context.bot.send_message(user2, "💌 You're now chatting anonymously. Type /stop to end.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid in chat_pairs:
        partner = chat_pairs.pop(uid)
        chat_pairs.pop(partner, None)

        await context.bot.send_message(partner, "❌ Your partner has left the chat.")
        await update.message.reply_text("🚪 You left the chat.")
    else:
        await update.message.reply_text("You're not in a chat. Type /start to find a partner.")

async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in chat_pairs:
        receiver = chat_pairs[uid]
        await context.bot.send_message(receiver, update.message.text)
    else:
        await update.message.reply_text("😕 You're not in a chat. Use /start to find someone.")

def main():
    app = Application.builder().token("YOUR_BOT_TOKEN").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    print("💘 MateFinder Bot is Live!")
    app.run_polling()

if __name__ == "__main__":
    main()
