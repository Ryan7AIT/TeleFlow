import os
from dotenv import load_dotenv
from typing import Final
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from message_handler import CustomMessageHandler
from state import user_states, ConversationState, load_commands, commands
from auth_handler import AuthHandler

load_dotenv()
TOKEN: Final = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_USERNAME: Final = os.getenv("TELEGRAM_BOT_USERNAME")

# Initialize auth handler
auth_handler = AuthHandler()

# Login conversation states (0,1)
USERNAME, PASSWORD = range(2)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello there! I'm your assistant today. How can I help you?")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I'm here to help! Just ask me a question or send me a voice message.")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    if chat_id in user_states:
        del user_states[chat_id]
        await update.message.reply_text("Conversation reset. You can start a new command.", 
                                      reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("No active conversation to reset.")

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the login process."""
    telegram_id = str(update.effective_user.id)
    
    # Check if already logged in
    if auth_handler.is_user_logged_in(telegram_id):
        await update.message.reply_text("You are already logged in! You can start using the bot.")
        return ConversationHandler.END
    
    await update.message.reply_text("Please enter your username:")
    return USERNAME

async def username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle username input and ask for password."""
    context.user_data['username'] = update.message.text
    await update.message.reply_text("Please enter your password:")
    return PASSWORD #next state (1)

async def password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle password input and complete login."""
    # Delete the message containing the password for security
    await update.message.delete()
    
    telegram_id = str(update.effective_user.id)
    username = context.user_data['username']
    password = update.message.text
    
    success, message = auth_handler.login_user(telegram_id, username, password)
    await update.message.reply_text(message)
    
    # Clear stored credentials from context
    if 'username' in context.user_data:
        del context.user_data['username']
    
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the login process."""
    await update.message.reply_text("Login cancelled. You can try again later using /login")
    return ConversationHandler.END

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    if auth_handler.logout_user(telegram_id):
        await update.message.reply_text("You have been logged out successfully.")
    else:
        await update.message.reply_text("You are not logged in.")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')

if __name__ == "__main__":
    print("Starting bot...")
    load_commands()
    app = Application.builder().token(TOKEN).build()

    # Initialize message handler
    message_handler = CustomMessageHandler(commands, BOT_USERNAME, auth_handler)

    # Login conversation handler
    login_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login_command)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username_handler)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("logout", logout_command))
    app.add_handler(login_handler)

    # Messages
    app.add_handler(MessageHandler(filters.TEXT | filters.VOICE, message_handler.process_message))

    # Errors
    app.add_error_handler(error)

    print("Polling...")
    app.run_polling(poll_interval=1)

