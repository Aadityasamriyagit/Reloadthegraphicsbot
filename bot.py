import logging
import asyncio
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, Defaults
from telegram.error import RetryAfter, TimedOut, NetworkError
from apscheduler.schedulers.asyncio import AsyncIOScheduler # For data cleanup

import config # Import your config
import data_manager
from scraper import (
    get_movie_source_websites,
    search_movie_on_site,
    get_movie_download_options,
    get_final_vcloud_download_link
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# httpx_logger = logging.getLogger("httpx") # For python-telegram-bot's HTTP client
# httpx_logger.setLevel(logging.WARNING) # Reduce verbosity of PTB's internal logs
logger = logging.getLogger(__name__)


# --- Constants ---
MAX_BUTTON_TEXT_LENGTH = 60 # Max characters for button text to avoid Telegram errors
MAX_RESULTS_TO_SHOW = 10    # Limit number of search results shown as buttons
MAX_OPTIONS_TO_SHOW = 10    # Limit number of download options shown


# --- Utility Functions ---
def truncate_text(text, length):
    return text[:length-3] + "..." if len(text) > length else text

async def send_message_with_retry(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs):
    """Sends a message with retry logic for common Telegram errors."""
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except RetryAfter as e:
        logger.warning(f"Rate limit hit (RetryAfter): sleeping for {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except (TimedOut, NetworkError) as e:
        logger.error(f"Telegram API timeout/network error: {e}. Retrying once.")
        await asyncio.sleep(5) # Wait a bit before retrying
        await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}", exc_info=True)
        raise # Re-raise other exceptions

async def edit_message_with_retry(query: Update.callback_query, text: str, **kwargs):
    """Edits a message with retry logic."""
    try:
        await query.edit_message_text(text=text, **kwargs)
    except RetryAfter as e:
        logger.warning(f"Rate limit hit on edit (RetryAfter): sleeping for {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        await query.edit_message_text(text=text, **kwargs)
    except (TimedOut, NetworkError) as e:
        logger.error(f"Telegram API timeout/network error on edit: {e}. Retrying once.")
        await asyncio.sleep(5)
        await query.edit_message_text(text=text, **kwargs)
    except Exception as e:
        # If the original message to edit is gone, or other error
        logger.error(f"Failed to edit message for query {query.id}: {e}", exc_info=True)
        # Fallback: send a new message if edit fails catastrophically
        try:
            await query.message.reply_text(text=text, **kwargs)
        except Exception as e_reply:
            logger.error(f"Fallback reply also failed for query {query.id}: {e_reply}", exc_info=True)


# --- Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    welcome_message = (
        f"Welcome to {config.BOT_NAME}! "
        "Just type the name of any movie you want and I will find it for you."
    )
    data_manager.clear_user_data(update.effective_chat.id) # Clear any previous stale data
    await send_message_with_retry(context, update.effective_chat.id, welcome_message)


async def handle_movie_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user's movie name input."""
    chat_id = update.effective_chat.id
    movie_name = update.message.text.strip()

    if not movie_name:
        await send_message_with_retry(context, chat_id, "Please provide a movie name.")
        return

    # Clear previous search data for this user before starting a new one
    data_manager.clear_user_data(chat_id)
    data_manager.store_user_data(chat_id, 'movie_name', movie_name)
    
    status_message = await context.bot.send_message(
        chat_id,
        f"Understood! I'm now searching for '{movie_name}' from my resources. This might take a moment..."
    )

    try:
        # 1. Get source websites
        source_sites_urls = await get_movie_source_websites(config.VGLIST_URL)
        if not source_sites_urls:
            await edit_message_with_retry(status_message.reply_to_message, text=f"Sorry, I couldn't access my list of movie resources at the moment. Please try again later.")
            return

        all_search_results = []
        search_tasks = [search_movie_on_site(site_url, movie_name) for site_url in source_sites_urls]
        
        site_results_list = await asyncio.gather(*search_tasks, return_exceptions=True)

        for i, res_list_or_exc in enumerate(site_results_list):
            site_url = source_sites_urls[i]
            if isinstance(res_list_or_exc, list):
                all_search_results.extend(res_list_or_exc)
            elif isinstance(res_list_or_exc, Exception):
                logger.error(f"Error during search on {site_url}: {res_list_or_exc}")
            else: # Should not happen
                logger.warning(f"Unexpected result type from search_movie_on_site for {site_url}: {type(res_list_or_exc)}")


        if not all_search_results:
            await status_message.edit_text(
                text=f"Sorry, I couldn't find '{movie_name}' from my available resources. Try checking the spelling or a different movie."
            )
            return

        # Store results with unique IDs for callback
        indexed_results = {}
        for result in all_search_results[:MAX_RESULTS_TO_SHOW]: # Limit results
            result_id = str(uuid.uuid4())[:8] # Short unique ID
            result['id'] = result_id # Add ID to the result dict
            indexed_results[result_id] = result
        
        data_manager.store_user_data(chat_id, 'search_results', indexed_results)
        
        keyboard = []
        for res_id, res_data in indexed_results.items():
            button_text = truncate_text(res_data['title'], MAX_BUTTON_TEXT_LENGTH)
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"movie_{res_id}")])
        
        if not keyboard:
             await status_message.edit_text(text=f"I found some information for '{movie_name}', but couldn't prepare selection options. Please try again.")
             return

        reply_markup = InlineKeyboardMarkup(keyboard)
        await status_message.edit_text(
            text=f"Here's what I found for '{movie_name}'. Please select one (showing up to {MAX_RESULTS_TO_SHOW} results):",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in handle_movie_name_input for '{movie_name}': {e}", exc_info=True)
        try: # Try to edit the status message if it exists
            await status_message.edit_text(text=f"Oops! Something went wrong while I was searching for '{movie_name}'. Please try again.")
        except: # Fallback if status_message doesn't exist or edit fails
            await send_message_with_retry(context, chat_id, f"Oops! Something went wrong while I was searching for '{movie_name}'. Please try again.")


# --- Callback Query Handlers ---
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer() # Acknowledge callback to remove "loading" state on button

    chat_id = query.effective_chat.id
    callback_data = query.data
    
    movie_name = data_manager.get_user_data(chat_id, 'movie_name')
    if not movie_name:
        await edit_message_with_retry(query, text="My memory of your search has expired or was cleared. Please start a new search.")
        return

    try:
        if callback_data.startswith("movie_"):
            selected_movie_id = callback_data.split("_")[1]
            search_results = data_manager.get_user_data(chat_id, 'search_results')
            
            if not search_results or selected_movie_id not in search_results:
                await edit_message_with_retry(query, text="Sorry, I couldn't find that specific movie selection. It might have expired. Please try searching again.")
                return
            
            selected_movie = search_results[selected_movie_id]
            data_manager.store_user_data(chat_id, 'selected_movie_details', selected_movie) # Store for next step

            await edit_message_with_retry(query, text=f"Great! Fetching download options for '{truncate_text(selected_movie['title'], 100)}'...")

            download_options = await get_movie_download_options(selected_movie['detail_page_url'], selected_movie['source_site'])

            if not download_options:
                await edit_message_with_retry(query, text=f"Sorry, I couldn't find any download options for '{truncate_text(selected_movie['title'], 100)}' from my resources.")
                return

            indexed_options = {}
            keyboard = []
            for option in download_options[:MAX_OPTIONS_TO_SHOW]: # Limit options
                option_id = str(uuid.uuid4())[:8]
                option['id'] = option_id # Add ID to option dict
                indexed_options[option_id] = option
                button_text = truncate_text(f"{option['quality']} - {option['language']}", MAX_BUTTON_TEXT_LENGTH)
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"option_{option_id}")])
            
            data_manager.store_user_data(chat_id, 'download_options_indexed', indexed_options)

            if not keyboard:
                await edit_message_with_retry(query, text=f"I found some details for '{truncate_text(selected_movie['title'], 100)}', but no specific download qualities/languages were listed.")
                return

            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_message_with_retry(
                query,
                text=f"Available download options for '{truncate_text(selected_movie['title'], 100)}' (showing up to {MAX_OPTIONS_TO_SHOW}):",
                reply_markup=reply_markup
            )

        elif callback_data.startswith("option_"):
            selected_option_id = callback_data.split("_")[1]
            selected_movie = data_manager.get_user_data(chat_id, 'selected_movie_details')
            download_options_indexed = data_manager.get_user_data(chat_id, 'download_options_indexed')

            if not selected_movie or not download_options_indexed or selected_option_id not in download_options_indexed:
                await edit_message_with_retry(query, text="Sorry, I couldn't process that selection. It might have expired. Please try searching again.")
                return

            selected_option = download_options_indexed[selected_option_id]
            
            await edit_message_with_retry(
                query,
                text=f"Excellent choice: {selected_option['quality']} - {selected_option['language']} for '{truncate_text(selected_movie['title'], 100)}'.\n"
                     f"I'm now trying to get the direct download link from the best available server. This can take a moment..."
            )

            final_download_link = await get_final_vcloud_download_link(selected_option['download_trigger_url'], selected_movie['source_site'])

            if final_download_link:
                # Ensure link is not too long for Telegram URL button
                if len(final_download_link) > constants.MessageLimit.URL_LENGTH:
                    logger.warning(f"Download link too long for button: {final_download_link}")
                    await edit_message_with_retry(
                        query,
                        text=f"The download link for '{truncate_text(selected_movie['title'], 50)}' ({selected_option['quality']} - {selected_option['language']}) is ready, but too long for a button. Here it is:\n{final_download_link}"
                    )
                else:
                    keyboard = [[InlineKeyboardButton("📥 Download Now", url=final_download_link)]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await edit_message_with_retry(
                        query,
                        text=f"Here is your download link for '{truncate_text(selected_movie['title'], 50)}' ({selected_option['quality']} - {selected_option['language']}):",
                        reply_markup=reply_markup
                    )
            else:
                await edit_message_with_retry(
                    query,
                    text=f"I'm sorry, I wasn't able to retrieve a direct download link for '{truncate_text(selected_movie['title'], 50)}' "
                         f"({selected_option['quality']} - {selected_option['language']}) at this time. "
                         "The servers might be busy, or the link couldn't be extracted automatically. "
                         "You might try a different option or try again later."
                )
            # Clear data for this specific completed search to free memory sooner
            # The global cleanup will still run for abandoned searches
            data_manager.clear_user_data(chat_id)


    except Exception as e:
        logger.error(f"Error in button_callback_handler for data '{callback_data}': {e}", exc_info=True)
        try:
            await edit_message_with_retry(query, text="Oops! Something went wrong with that selection. Please try again or start a new search.")
        except Exception: # If original message was deleted or something
            await send_message_with_retry(context, chat_id, text="Oops! Something went wrong. Please try again or start a new search.")


def main() -> None:
    """Start the bot and the data cleanup scheduler."""
    
    if config.TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or not config.TELEGRAM_BOT_TOKEN:
        logger.critical("CRITICAL: TELEGRAM_BOT_TOKEN is not configured. Please set it in config.py or as an environment variable.")
        return

    # Set defaults for all handlers (e.g., parse_mode)
    defaults = Defaults(parse_mode=constants.ParseMode.HTML) # Or MARKDOWN
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).defaults(defaults).build()

    # --- Register Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_movie_name_input))
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # --- Start Data Cleanup Scheduler ---
    scheduler = AsyncIOScheduler(timezone="UTC")
    # Run cleanup_expired_data every hour, but also immediately on start for any stale data from previous runs
    scheduler.add_job(data_manager.cleanup_expired_data, 'interval', hours=1, misfire_grace_time=300, id="hourly_cleanup")
    scheduler.add_job(data_manager.cleanup_expired_data, 'date', run_date=None, id="initial_cleanup") # Runs once on start
    
    try:
        scheduler.start()
        logger.info("Data cleanup scheduler started.")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)


    logger.info(f"{config.BOT_NAME} is starting... Polling for updates.")
    
    # Install Playwright browsers if not already installed (optional, better to do it manually once)
    # This is a blocking call, so usually done outside the main async flow or as a pre-start script
    # For simplicity here, it's just a print reminder.
    logger.info("Ensure Playwright browsers are installed by running: playwright install chromium")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

    # On bot shutdown (e.g., Ctrl+C)
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Data cleanup scheduler stopped.")


if __name__ == "__main__":
    main()