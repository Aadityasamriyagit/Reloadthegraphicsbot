import time
import threading
from config import DATA_EXPIRY_SECONDS # Assuming config.py is in the same directory

# In-memory storage. For persistence across restarts, use a DB.
user_search_data = {} # {chat_id: {'timestamp': float, 'data': { ... }}}

# Lock for thread-safe access to user_search_data
data_lock = threading.Lock()

def store_user_data(chat_id, key, value):
    with data_lock:
        if chat_id not in user_search_data:
            user_search_data[chat_id] = {'timestamp': time.time(), 'data': {}}
        else: # Update timestamp on new activity for this user
            user_search_data[chat_id]['timestamp'] = time.time()
        user_search_data[chat_id]['data'][key] = value

def get_user_data(chat_id, key):
    with data_lock:
        if chat_id in user_search_data:
            return user_search_data[chat_id]['data'].get(key)
        return None

def clear_user_data(chat_id):
    with data_lock:
        if chat_id in user_search_data:
            del user_search_data[chat_id]
            print(f"Cleared data for chat_id: {chat_id}")


def cleanup_expired_data():
    """
    Cleans up data for users whose records have expired.
    This function is intended to be called periodically by a scheduler.
    """
    with data_lock:
        current_time = time.time()
        expired_users = [
            chat_id for chat_id, record in user_search_data.items()
            if current_time - record['timestamp'] > DATA_EXPIRY_SECONDS
        ]
        for chat_id in expired_users:
            print(f"Cleaning up EXPIRED data for chat_id: {chat_id}")
            if chat_id in user_search_data: # Check again due to potential race condition if lock was finer-grained
                del user_search_data[chat_id]
    
    # Note: The actual scheduling of this function (e.g., using APScheduler)
    # will be handled in bot.py. This function itself just performs the cleanup.
    print(f"Cleanup task ran. Current user data keys: {list(user_search_data.keys())}")

# Example: If you wanted to run this periodically with threading.Timer (less ideal for asyncio bots)
# def schedule_cleanup():
#     cleanup_expired_data()
#     # Reschedule the cleanup
#     # For an asyncio bot, APScheduler in bot.py is preferred
#     threading.Timer(3600, schedule_cleanup).start() # Check every hour

# if __name__ == "__main__":
    # This part is for testing the data manager independently.
    # In the actual bot, APScheduler will call cleanup_expired_data.
    # print("Starting data manager test cleanup scheduler...")
    # schedule_cleanup()
    # store_user_data(123, "movie", "Test Movie")
    # print(get_user_data(123, "movie"))
    # time.sleep(5) # Keep alive for a bit
    # clear_user_data(123)
    # print(get_user_data(123, "movie"))