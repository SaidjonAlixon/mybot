import os
import json
import threading # Import threading
from flask import Flask # Import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, ChatMemberHandler, MessageHandler, filters

# --- IMPORTANT: REPLACE THESE PLACEHOLDERS ---
# Get your bot token from @BotFather on Telegram.
TOKEN = os.environ.get("TOKEN")
# Get your admin chat ID from a bot like @userinfobot. This is where new user notifications will be sent.
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID")) # Example: 123456789 (must be an integer)
# Replace with the URL of your web application.
WEB_APP_URL = os.environ.get("WEB_APP_URL")
# --- END OF PLACEHOLDERS ---

USER_DATA_FILE = 'user_data.json'
user_numbers = {} # Stores user_id: assigned_number
subscribers = set() # Stores unique user_ids
next_user_number = 1

# Flask app for keeping the bot alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask_app():
    # Use 0.0.0.0 to make it accessible from outside the container (for Replit, etc.)
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080)) # Replit uses PORT env variable

def load_user_data():
    global user_numbers, subscribers, next_user_number
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            data = json.load(f)
            user_numbers = {int(k): v for k, v in data.get('user_numbers', {}).items()}
            subscribers = set(data.get('subscribers', []))
            if user_numbers:
                next_user_number = max(user_numbers.values()) + 1
            else:
                next_user_number = 1
    else:
        user_numbers = {}
        subscribers = set()
        next_user_number = 1

def save_user_data():
    with open(USER_DATA_FILE, 'w') as f:
        json.dump({
            'user_numbers': user_numbers,
            'subscribers': list(subscribers),
            'next_user_number': next_user_number
        }, f, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message and requests phone number if not already shared."""
    user = update.effective_user
    user_id = user.id

    # Assign a unique number to the user if they are new to the bot
    if user_id not in user_numbers:
        global next_user_number
        user_numbers[user_id] = next_user_number
        subscribers.add(user_id)
        next_user_number += 1
        save_user_data()

    # Check if contact information has been shared before for this user
    if context.user_data.get('has_shared_contact'):
        keyboard = [
            [InlineKeyboardButton("Web Ilovani Ochish", web_app=WebAppInfo(url=WEB_APP_URL))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Xush kelibsiz! Web ilovani ochish uchun quyidagi tugmani bosing:",
            reply_markup=reply_markup
        )
    else:
        # Request phone number if not shared yet
        keyboard = [
            [KeyboardButton("Raqamimni ulashish", request_contact=True)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "Xush kelibsiz! Web ilovani ochishdan oldin iltimos, telefon raqamingizni ulashing:",
            reply_markup=reply_markup
        )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles shared contact information and notifies admin."""
    user = update.effective_user
    user_id = user.id
    phone_number = update.message.contact.phone_number

    # Ensure user has a number and is in subscribers
    if user_id not in user_numbers:
        global next_user_number
        user_numbers[user_id] = next_user_number
        subscribers.add(user_id)
        next_user_number += 1
        save_user_data()

    current_user_num = user_numbers[user_id]

    # Store that contact has been shared for this user
    context.user_data['has_shared_contact'] = True

    user_info = user.first_name
    if user.last_name:
        user_info += f" {user.last_name}"
    if user.username:
        user_info += f" (@{user.username})"

    message_text = (
        f"🎉 Yangi foydalanuvchi ma'lumotlari: {user_info} (ID: {user_id}), Raqami: {current_user_num}\n"
        f"Telefon raqami: {phone_number}\n"
        f"Chat: {update.effective_chat.title if update.effective_chat.title else 'Shaxsiy Chat'}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message_text)
        print(f"Admin notified about new user (via contact): {user_info}, Number: {current_user_num}, Phone: {phone_number}")
    except Exception as e:
        print(f"Failed to send admin notification (via contact): {e}")

    # Send the main welcome message with Web App button and remove the contact keyboard
    keyboard = [
        [InlineKeyboardButton("Web Ilovani Ochish", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Raqamingiz qabul qilindi. Web ilovani ochish uchun quyidagi tugmani bosing:",
        reply_markup=reply_markup
    )
    # Explicitly remove the reply keyboard after the contact is handled
    await update.message.reply_text(
        "Davom etishingiz mumkin.",
        reply_markup=ReplyKeyboardRemove()
    )


async def new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notifies the admin when a new user joins the chat."""
    if update.effective_chat.type in ["group", "supergroup"]:
        for member in update.effective_chat.new_chat_members:
            if not member.is_bot:
                user_id = member.id
                if user_id not in user_numbers:
                    global next_user_number
                    user_numbers[user_id] = next_user_number
                    subscribers.add(user_id)
                    current_user_num = next_user_number
                    next_user_number += 1
                    save_user_data()
                else:
                    current_user_num = user_numbers[user_id]

                user_info = member.first_name
                if member.last_name:
                    user_info += f" {member.last_name}"
                if member.username:
                    user_info += f" (@{member.username})"

                message_text = (
                    f"🎉 Yangi foydalanuvchi qo'shildi: {user_info} (ID: {user_id}), Raqami: {current_user_num}\n"
                    f"Guruh/Shaxsiy Chat: {update.effective_chat.title if update.effective_chat.title else 'Shaxsiy Chat'}"
                )
                try:
                    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message_text)
                    print(f"Admin notified about new user: {user_info}, Number: {current_user_num}")
                except Exception as e:
                    print(f"Failed to send admin notification: {e}")
    else:
        pass

async def show_subscribers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the total number of active subscribers to the admin."""
    if update.effective_user.id == ADMIN_CHAT_ID:
        await update.message.reply_text(f"📊 Faol obunachilar soni: {len(subscribers)}")
    else:
        await update.message.reply_text("Sizga bu buyruqni ishlatishga ruxsat berilmagan.")

def main() -> None:
    """Starts the bot."""
    # Start the Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()

    load_user_data() # Load data on bot start
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact)) # New handler for contact
    application.add_handler(ChatMemberHandler(new_chat_member, ChatMemberHandler.CHAT_MEMBER))
    application.add_handler(CommandHandler("subscribers", show_subscribers)) # New handler for admin command

    print("Bot polling started. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
