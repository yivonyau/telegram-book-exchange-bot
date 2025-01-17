# Book Exchange Bot
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import gspread
from google.oauth2.service_account import Credentials

# States for conversation
PHOTO, TITLE, CONDITION = range(3)

# Setup Google Sheets connection
def setup_sheets():
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file('credentials.json', scopes=scope)
    client = gspread.authorize(creds)
    return client.open('Book Exchange System').sheet1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
Welcome to Class Book Exchange! 📚

Available commands:
/register - Add a new book
/list - See available books
/borrow - Borrow a book
/return - Return a book
/help - Show this help message
    """
    await update.message.reply_text(welcome_message)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the registration process"""
    await update.message.reply_text("Please send a photo of the book 📸")
    return PHOTO

async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received photo"""
    photo_file = await update.message.photo[-1].get_file()
    photo_path = f"photos/{update.message.from_user.id}_{update.message.message_id}.jpg"
    await photo_file.download_to_drive(photo_path)
    context.user_data['photo_path'] = photo_path
    
    await update.message.reply_text("Great! Now please send the book title 📖")
    return TITLE

async def title_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received title"""
    context.user_data['title'] = update.message.text
    
    keyboard = [['Like New', 'Good', 'Fair']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(
        "What's the condition of the book?",
        reply_markup=reply_markup
    )
    return CONDITION

async def condition_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle received condition and complete registration"""
    sheet = setup_sheets()
    
    # Save to Google Sheet
    sheet.append_row([
        context.user_data['title'],
        update.message.from_user.id,
        update.message.text,  # condition
        'Available',
        context.user_data['photo_path']
    ])
    
    await update.message.reply_text(
        f"✅ Book registered successfully!\n"
        f"Title: {context.user_data['title']}\n"
        f"Condition: {update.message.text}"
    )
    return ConversationHandler.END

async def list_books(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available books"""
    sheet = setup_sheets()
    books = sheet.get_all_records()
    
    available_books = [book for book in books if book['Status'] == 'Available']
    
    if not available_books:
        await update.message.reply_text("No books available at the moment.")
        return
    
    message = "📚 Available Books:\n\n"
    for i, book in enumerate(available_books, 1):
        message += f"{i}. {book['Title']} ({book['Condition']})\n"
    
    await update.message.reply_text(message)

async def borrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle book borrowing"""
    args = context.args
    if not args:
        await update.message.reply_text("Please use: /borrow [book number]")
        return
    
    try:
        book_num = int(args[0])
        sheet = setup_sheets()
        books = sheet.get_all_records()
        available_books = [b for b in books if b['Status'] == 'Available']
        
        if 0 < book_num <= len(available_books):
            book = available_books[book_num - 1]
            # Update book status
            row = books.index(book) + 2
            sheet.update_cell(row, 4, 'Borrowed')
            sheet.update_cell(row, 5, str(update.message.from_user.id))
            
            await update.message.reply_text(
                f"✅ You've borrowed: {book['Title']}\n"
                f"Please take good care of the book!"
            )
        else:
            await update.message.reply_text("Invalid book number. Please check /list and try again.")
    
    except ValueError:
        await update.message.reply_text("Please provide a valid book number.")

async def return_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle book return"""
    sheet = setup_sheets()
    books = sheet.get_all_records()
    
    borrowed_books = [b for b in books if b['Status'] == 'Borrowed' 
                     and b['Borrower'] == str(update.message.from_user.id)]
    
    if not borrowed_books:
        await update.message.reply_text("You haven't borrowed any books.")
        return
    
    message = "Your borrowed books:\n\n"
    for i, book in enumerate(borrowed_books, 1):
        message += f"{i}. {book['Title']}\n"
    message += "\nTo return a book, use: /return [book number]"
    
    await update.message.reply_text(message)

def main():
    """Start the bot"""
    # Create application and pass bot token
    application = Application.builder().token('7425993280:AAGtMx4rjt7nzq9oHngyQonps2fvYzNYVXg').build()
    
    # Add conversation handler for book registration
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('register', register)],
        states={
            PHOTO: [MessageHandler(filters.PHOTO, photo_received)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, title_received)],
            CONDITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, condition_received)]
        },
        fallbacks=[]
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("list", list_books))
    application.add_handler(CommandHandler("borrow", borrow))
    application.add_handler(CommandHandler("return", return_book))
    application.add_handler(conv_handler)
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
