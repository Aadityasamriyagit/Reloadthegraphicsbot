# config.py.example
# Rename this file to config.py and fill in your actual values.
# DO NOT commit your actual config.py with sensitive credentials to a public repository.
# The .gitignore file is set up to ignore config.py.

import os

# --- Bot Configuration ---
# Get your Telegram Bot Token from BotFather
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# The URL from which to fetch the list of movie source websites.
# This is a placeholder; you'll need to determine the actual URL or method.
VGLIST_URL = "https://vglist.nl/" # Or your specific target for source site list

# Bot's display name (used in messages)
BOT_NAME = "Load The Graphics Bot"

# --- Data Management ---
# How long to keep user search data in memory (in seconds)
# 2 hours = 2 * 60 * 60
DATA_EXPIRY_SECONDS = 7200

# --- Scraping Configuration ---
# (You might add more scraper-specific configurations here if needed)

# Example of how to ensure the token is set:
if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE" and not os.environ.get('TELEGRAM_BOT_TOKEN'):
    print("ERROR: TELEGRAM_BOT_TOKEN is not set in config.py or as an environment variable.")
    print("Please get a token from BotFather and add it to config.py or set the TELEGRAM_BOT_TOKEN environment variable.")
    # You might want to exit here in a real application if the token is missing
    # import sys
    # sys.exit(1)