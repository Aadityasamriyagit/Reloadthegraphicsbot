# Load The Graphics Bot

A Telegram bot designed to search for movies and provide download links by scraping various websites.

**Disclaimer:** This bot framework is provided for educational purposes. Scraping websites can be against their Terms of Service. Downloading copyrighted material without permission is illegal in many countries. Use responsibly and ethically. The scraping logic for specific movie sites in `scraper.py` is **placeholder** and requires custom implementation.

## Features (Planned)

*   Responds to `/start` with a welcome message.
*   Accepts movie name input from users.
*   (Placeholder) Fetches a list of source movie websites (conceptually from vglist.nl).
*   (Placeholder) Searches each source website for the movie.
*   (Placeholder) Scrapes movie titles, posters, and detail page links.
*   Turns on an ad blocker while browsing.
*   Shows search results as interactive buttons.
*   (Placeholder) Fetches download options (quality, language) for a selected movie.
*   Shows download options as interactive buttons.
*   (Placeholder) Navigates to VCloud server pages and prioritizes specific servers for the final download link.
*   Provides a "Download Now" button with the direct link.
*   Temporarily stores search data and auto-deletes it after 2 hours.

## Setup and Installation

1.  **Clone the repository (or download and extract the ZIP):**
    If you downloaded a ZIP, extract it. If you are cloning:
    ```bash
    git clone https://github.com/YOUR_USERNAME/load-the-graphics-bot.git
    cd load-the-graphics-bot
    ```

2.  **Create a Python virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright browsers:**
    ```bash
    playwright install chromium
    ```
    (This bot is configured to use Chromium. You can install others if needed: `playwright install`)

5.  **Configure the Bot:**
    *   Rename `config.py.example` to `config.py`.
    *   Open `config.py` and add your `TELEGRAM_BOT_TOKEN`. You can get this from BotFather on Telegram.
    *   Review other settings in `config.py`.
    *   **IMPORTANT:** If your repository is public, **DO NOT** commit your actual `config.py` file with the token. The `.gitignore` file is set up to ignore `config.py`. Use environment variables for deployment.

6.  **Implement Scraping Logic:**
    *   The crucial step: Open `scraper.py`.
    *   You **MUST** fill in the placeholder sections (marked with `--- !!! REPLACE WITH ACTUAL SELECTORS ... !!! ---`) with Python Playwright code to interact with `vglist.nl` (if you choose to scrape it directly) and the actual movie source websites. This requires web development knowledge to inspect website HTML and identify the correct selectors and interaction flows.

7.  **Run the bot:**
    ```bash
    python bot.py
    ```

## Dependencies

*   `python-telegram-bot`
*   `playwright`
*   `apscheduler`

## Important Note on Scraping

The web scraping functions in `scraper.py` (`get_movie_source_websites`, `search_movie_on_site`, `get_movie_download_options`, `get_final_vcloud_download_link`) are currently **placeholders**. They will not work out-of-the-box. You or a developer will need to:

1.  Identify the actual movie source websites.
2.  For each website:
    *   Inspect its HTML structure.
    *   Write specific Playwright code to navigate, search, and extract the required information (movie titles, poster URLs, detail page URLs, download options, VCloud server links).
    *   Handle ads, pop-ups, and anti-bot measures.
3.  This part requires significant development effort and ongoing maintenance as websites change.

---
Made with the conceptual help of an AI assistant.