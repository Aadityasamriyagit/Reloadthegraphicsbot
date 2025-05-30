from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import re
import logging
# from bs4 import BeautifulSoup # If needed for complex HTML parsing after getting content

logger = logging.getLogger(__name__)

# --- Ad Blocking Helper ---
# A simple list of patterns. A more robust solution would use a proper filter list.
# You can find public adblock filter lists (e.g., EasyList) and adapt patterns.
AD_DOMAINS_PATTERNS = [
    "doubleclick.net", "googleadservices.com", "googlesyndication.com",
    "adservice.google.com", ".cloudfront.net/ads", "adform.net", "adsrvr.org",
    "popads.net", "yllix.com", "propellerads.com", "adsterra.com",
    "onclickads.net", " ट्रैफिकjunky.com", "exoclick.com", "ero-advertising.com",
    "juicyads.com", "plugrush.com", "bongacams.com", "chaturbate.com"
    # Add more known ad/tracker domains or URL patterns
]

async def block_ads_route(route):
    """Intelligently blocks requests based on AD_DOMAINS_PATTERNS."""
    url = route.request.url
    resource_type = route.request.resource_type
    
    # Block common ad resource types or URLs matching patterns
    if resource_type in ["image", "script", "iframe", "media", "websocket"] and \
       any(pattern in url for pattern in AD_DOMAINS_PATTERNS):
        try:
            # logger.debug(f"Blocking ad request: {url[:80]}")
            await route.abort()
            return
        except Exception: # Request might already be handled or aborted
            pass # Silently ignore if abort fails
            return
            
    # Block pop-ups or new tabs that are likely ads
    # This is harder to do reliably with route interception alone
    # It's often better handled by Playwright's context options or page event listeners

    try:
        await route.continue_()
    except Exception: # Request might already be handled
        pass


async def get_playwright_page(context_options=None, playwright_instance=None):
    """
    Initializes Playwright (if not provided) and returns a new page with ad blocking.
    Returns: playwright, browser, context, page
    Manages playwright instance to avoid multiple starts/stops if called sequentially.
    """
    pw_instance = playwright_instance
    if pw_instance is None:
        pw_instance = await async_playwright().start()

    # browser = await pw_instance.chromium.launch(headless=True) # For production
    browser = await pw_instance.chromium.launch(headless=False, args=['--no-sandbox', '--disable-setuid-sandbox']) # For development/debugging & some CI

    # Create a new browser context with ad blocking
    # Consider other context options for robust ad blocking:
    # user_agent, viewport, permissions for notifications/popups, etc.
    default_context_options = {
        'java_script_enabled': True,
        'ignore_https_errors': True, # Some sites might have SSL issues
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
    }
    if context_options:
        default_context_options.update(context_options)
    
    context = await browser.new_context(**default_context_options)
    await context.route("**/*", block_ads_route) # More aggressive ad blocking

    # Handle new pages (pop-ups) - attempt to close ad pop-ups
    async def handle_popup(popup_page):
        # logger.debug(f"New page opened (potential popup): {popup_page.url}")
        # Simple check: if the URL is one of the ad domains, close it.
        # This is very basic and might close legitimate popups.
        if any(pattern in popup_page.url for pattern in AD_DOMAINS_PATTERNS):
            # logger.info(f"Closing likely ad popup: {popup_page.url}")
            try:
                await popup_page.close()
            except Exception as e:
                # logger.warning(f"Could not close popup {popup_page.url}: {e}")
                pass
        # else:
            # logger.debug(f"Allowing non-ad popup: {popup_page.url}")


    context.on("page", handle_popup) # Listen for new pages opened from this context

    page = await context.new_page()
    return pw_instance, browser, context, page

async def close_playwright_resources(browser, context=None, playwright_instance_provided=True):
    """Closes browser and context. Stops Playwright if it was started by get_playwright_page."""
    if context:
        try:
            await context.close()
        except Exception as e:
            logger.error(f"Error closing context: {e}")
    if browser:
        try:
            await browser.close()
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    # Only stop playwright if it was started within a scraper function call
    # and not passed in (meaning it's managed externally for multiple calls)
    # This logic might need refinement based on how playwright_instance is managed
    # For now, assume if playwright_instance_provided is False, it means it was started locally
    # if playwright_instance and not playwright_instance_provided:
    #     try:
    #         await playwright_instance.stop()
    #     except Exception as e:
    #         logger.error(f"Error stopping playwright: {e}")


async def get_movie_source_websites(vglist_url: str):
    """
    Scrapes vglist.nl (or the specified URL) to get a list of movie source websites.
    THIS IS A PLACEHOLDER - You need to implement the actual scraping logic.
    """
    logger.info(f"Fetching source websites from {vglist_url}...")
    playwright = None
    browser = None
    source_sites = []
    try:
        playwright, browser, context, page = await get_playwright_page()

        # --- !!! REPLACE WITH ACTUAL SELECTORS FOR vglist.nl !!! ---
        # Example: (Inspect vglist.nl to find correct selectors)
        # await page.goto(vglist_url, timeout=60000, wait_until='domcontentloaded')
        # await page.wait_for_load_state('networkidle', timeout=30000)
        # link_elements = await page.query_selector_all("div.movie-site-list a.site-link")
        # for link_el in link_elements:
        #     href = await link_el.get_attribute("href")
        #     if href and (href.startswith("http://") or href.startswith("https://")):
        #         source_sites.append(href)
        
        logger.warning("Using DUMMY source websites. Implement actual vglist.nl scraping in scraper.py.")
        await asyncio.sleep(0.1) # Simulate network
        source_sites = [
            "https://dummy-movie-site-alpha.com", # Replace with actual site URLs after discovery
            "https://dummy-movie-site-beta.com",
        ]
        if not source_sites:
            logger.warning("No source sites found on vglist.nl (or placeholder is empty).")

    except PlaywrightTimeoutError:
        logger.error(f"Timeout error scraping {vglist_url}")
    except Exception as e:
        logger.error(f"Error scraping {vglist_url}: {e}", exc_info=True)
    finally:
        if browser: await close_playwright_resources(browser, context, playwright_instance_provided=False if playwright else True)
        if playwright and not browser : await playwright.stop() # if browser init failed but pw started
    
    logger.info(f"Found source sites: {source_sites}")
    return source_sites


async def search_movie_on_site(site_url: str, movie_name: str):
    """
    Searches for a movie on a single given website and scrapes results.
    THIS IS A PLACEHOLDER - You need to implement logic for EACH site.
    Returns a list of dicts: {'title': str, 'poster_url': str, 'detail_page_url': str, 'source_site': str}
    """
    logger.info(f"Searching for '{movie_name}' on {site_url}...")
    playwright = None
    browser = None
    results = []
    max_retries = 1 # For handling ad clicks or initial load issues

    for attempt in range(max_retries + 1):
        page = None # ensure page is reset for retries
        try:
            playwright, browser, context, page = await get_playwright_page(playwright_instance=playwright) # Reuse playwright if already started
            
            # Navigate to site
            await page.goto(site_url, timeout=60000, wait_until='domcontentloaded')
            # A small delay or wait for a specific element can be more reliable than networkidle sometimes
            await page.wait_for_timeout(3000) # Wait for some initial scripts/ads to settle

            # --- !!! REPLACE WITH ACTUAL SELECTORS AND LOGIC FOR THE SPECIFIC SITE !!! ---
            # This logic will be different for EACH movie source website.
            # Example pseudo-code:
            search_bar_selector = 'input[name="q"], input[type="text"], input.search-input, #search_input, input[placeholder*="Search"]'
            # Be very specific if possible, e.g., page.locator('form[action*="search"] input[type="text"]').first
            
            # Try to fill search bar
            try:
                await page.locator(search_bar_selector).first.fill(movie_name, timeout=15000)
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout finding search bar on {site_url}. Trying alternative common selectors.")
                # Try more generic approaches if specific one fails
                common_search_inputs = await page.query_selector_all('input[type="text"], input[type="search"]')
                filled = False
                for s_input in common_search_inputs:
                    if await s_input.is_visible():
                        try:
                            await s_input.fill(movie_name, timeout=5000)
                            filled = True
                            logger.info(f"Filled search using generic input on {site_url}")
                            break
                        except:
                            continue
                if not filled:
                    logger.error(f"Could not find or fill search bar on {site_url} after retries.")
                    raise PlaywrightTimeoutError("Search bar not found or interactable.")


            # Submit search (Enter or click button)
            try:
                await page.keyboard.press("Enter")
                logger.info(f"Pressed Enter for search on {site_url}")
            except Exception as e_key:
                logger.warning(f"Could not press Enter on {site_url} ({e_key}). Trying to find a search button.")
                search_button_selector = 'button[type="submit"], button.search-button, button:has-text("Search"), a.search-button'
                try:
                    await page.locator(search_button_selector).first.click(timeout=10000)
                    logger.info(f"Clicked search button on {site_url}")
                except PlaywrightTimeoutError:
                    logger.error(f"Could not find or click search button on {site_url} after trying Enter.")
                    # Continue, some sites search dynamically
            
            await page.wait_for_load_state('domcontentloaded', timeout=30000)
            await page.wait_for_timeout(5000) # Wait for results to load via JS

            # --- Check for ad redirect or failed search ---
            current_url = page.url
            if site_url not in current_url and not current_url.startswith(site_url) and attempt < max_retries:
                logger.warning(f"Possible ad redirect on {site_url}. Current URL: {current_url}. Retrying (attempt {attempt+1})...")
                if browser: await close_playwright_resources(browser, context, playwright_instance_provided=True) # Close current browser before retry
                browser = None # ensure new browser for retry
                playwright = None # ensure new playwright for retry
                await asyncio.sleep(2)
                continue # Retry the search

            # --- Scrape results (highly site-specific) ---
            # result_item_selector = "div.movie-item, li.search-result, article.movie-entry" # Example
            # title_selector = "h3.title a, span.title, .movie-name"
            # poster_selector = "img.poster, .movie-poster img"
            # detail_link_selector = "a.watch-now, .movie-link"
            
            # --- DUMMY RESULTS FOR NOW (REPLACE THIS) ---
            logger.warning(f"Using DUMMY search results for {site_url}. Implement actual scraping.")
            if "dummy-movie-site-alpha" in site_url:
                for i in range(1): # Simulate finding 1 result
                    results.append({
                        'title': f"{movie_name} - Result {i+1} (Alpha Site)",
                        'poster_url': f"https://via.placeholder.com/150x220.png?text={movie_name.replace(' ','+')}+{i+1}",
                        'detail_page_url': f"{site_url}/movie/{movie_name.replace(' ','-').lower()}-details-{i+1}",
                        'source_site': site_url
                    })
            elif "dummy-movie-site-beta" in site_url:
                results.append({
                    'title': f"{movie_name} - Result (Beta Site)",
                    'poster_url': f"https://via.placeholder.com/150x220.png?text={movie_name.replace(' ','+')}+Beta",
                    'detail_page_url': f"{site_url}/view/{movie_name.replace(' ','_').lower()}",
                    'source_site': site_url
                })
            # --- END OF DUMMY RESULTS ---
            
            if results: # If results found, break retry loop
                break

        except PlaywrightTimeoutError as pte:
            logger.error(f"Timeout during search on {site_url} (attempt {attempt+1}): {pte}")
        except Exception as e:
            logger.error(f"Generic error searching on {site_url} (attempt {attempt+1}): {e}", exc_info=True)
        
        if attempt < max_retries and not results: # If error and retries left
            logger.info(f"Retrying search on {site_url}...")
            if browser: await close_playwright_resources(browser, context, playwright_instance_provided=True)
            browser = None
            playwright = None
            await asyncio.sleep(3) # Wait a bit before retrying
        else: # Last attempt or success
            break

    if browser: await close_playwright_resources(browser, context, playwright_instance_provided=True)
    if playwright and not browser: await playwright.stop()

    logger.info(f"Found {len(results)} results on {site_url} for '{movie_name}'.")
    return results


async def get_movie_download_options(detail_page_url: str, source_site: str):
    """
    Visits the movie detail page and scrapes available download options (quality, language).
    THIS IS A PLACEHOLDER - Highly site-specific.
    Returns a list of dicts: {'quality': str, 'language': str, 'download_trigger_url': str}
    'download_trigger_url' is the URL that leads to the VCloud server selection page or triggers the download process.
    """
    logger.info(f"Fetching download options from {detail_page_url}...")
    playwright = None
    browser = None
    options = []
    try:
        playwright, browser, context, page = await get_playwright_page()
        await page.goto(detail_page_url, timeout=60000, wait_until='domcontentloaded')
        await page.wait_for_timeout(5000) # Allow JS to load dynamic content

        # --- !!! REPLACE WITH ACTUAL SELECTORS FOR THE SPECIFIC SITE !!! ---
        # Example pseudo-code:
        # option_item_selector = "div.download-option, li.quality-link"
        # quality_selector = "span.quality, .quality-text"
        # language_selector = "span.language, .lang-text"
        # link_to_download_page_selector = "a.download-server-link, button.get-links"

        # --- DUMMY OPTIONS FOR NOW (REPLACE THIS) ---
        logger.warning(f"Using DUMMY download options for {detail_page_url}. Implement actual scraping.")
        if "dummy-movie-site-alpha" in source_site:
            options.extend([
                {'quality': '720p', 'language': 'English', 'download_trigger_url': f"{detail_page_url}/download?q=720&l=eng"},
                {'quality': '1080p', 'language': 'Dual Audio', 'download_trigger_url': f"{detail_page_url}/download?q=1080&l=dual"},
            ])
        elif "dummy-movie-site-beta" in source_site:
            options.append(
                {'quality': '1080p', 'language': 'English', 'download_trigger_url': f"{detail_page_url}/getlink?res=1080p"}
            )
        # --- END OF DUMMY OPTIONS ---
        
        logger.info(f"Found options: {options}")

    except PlaywrightTimeoutError as pte:
        logger.error(f"Timeout getting download options from {detail_page_url}: {pte}")
    except Exception as e:
        logger.error(f"Error getting download options from {detail_page_url}: {e}", exc_info=True)
    finally:
        if browser: await close_playwright_resources(browser, context, playwright_instance_provided=False if playwright else True)
        if playwright and not browser : await playwright.stop()
    return options


async def get_final_vcloud_download_link(download_trigger_url: str, source_site: str):
    """
    Navigates to the page with VCloud server options and extracts the prioritized download link.
    THIS IS A PLACEHOLDER - Extremely site-specific.
    Prioritizes: "Server One" > "FSL Server" > "10 Gbps Server"
    Returns the direct download URL string.
    """
    logger.info(f"Getting final VCloud link from {download_trigger_url}...")
    playwright = None
    browser = None
    final_link = None
    
    server_priority = [
        {"name": "Server One", "identifiers": ["Server One", "VCloud Server 1", "server-one-button", re.compile(r"server\s*1", re.I)]},
        {"name": "FSL Server", "identifiers": ["FSL Server", "Fast Server Link", "fsl-server-link", re.compile(r"fsl", re.I)]},
        {"name": "10 Gbps Server", "identifiers": ["10 Gbps Server", "10Gbps Speed", "high-speed-server", re.compile(r"10\s*gbps", re.I)]},
    ]

    try:
        playwright, browser, context, page = await get_playwright_page()
        await page.goto(download_trigger_url, timeout=60000, wait_until='domcontentloaded')
        await page.wait_for_timeout(7000) # Wait for servers/JS to load, ads to attempt load

        # --- !!! REPLACE WITH ACTUAL VCLOUD SERVER SELECTION LOGIC FOR THE SPECIFIC SITE !!! ---
        # This is the most complex part. You might need to:
        # 1. Find buttons/links for each server.
        # 2. Click the highest priority available one.
        # 3. Wait for a new page/element to appear, or handle new tabs.
        # 4. Extract the direct download link (often an .mp4, .mkv, etc.).
        #    This link might be in an `<a>` href, a `video` src, or dynamically generated after clicks.

        logger.warning(f"Using DUMMY VCloud link logic for {download_trigger_url}. Implement actual VCloud scraping.")

        # Example Pseudo-Logic (MUST BE TAILORED PER SITE):
        for server_pref in server_priority:
            logger.debug(f"Trying server: {server_pref['name']}")
            for identifier in server_pref['identifiers']:
                try:
                    server_element_locator = None
                    if isinstance(identifier, str):
                        # Try to find a clickable element: button, <a>, or div/span with relevant class/id/text
                        # More specific selectors are better
                        server_element_locator = page.locator(
                            f'button:has-text("{identifier}"), a:has-text("{identifier}"), '
                            f'[class*="{identifier}" i], [id*="{identifier}" i], '
                            f'div:has-text("{identifier}") >> nth=0, span:has-text("{identifier}") >> nth=0'
                        ).first
                    elif isinstance(identifier, re.Pattern):
                         server_element_locator = page.locator(
                            f'button:has-text({identifier}), a:has-text({identifier}), '
                            f'div:has-text({identifier}) >> nth=0, span:has-text({identifier}) >> nth=0'
                        ).first
                    
                    if server_element_locator and await server_element_locator.is_visible(timeout=5000):
                        logger.info(f"Found element for {server_pref['name']} using '{identifier}'")
                        
                        # OPTION A: Element itself is the download link
                        href = await server_element_locator.get_attribute("href")
                        if href and (href.endswith((".mp4", ".mkv", ".avi", ".webm")) or "googlevideo.com/videoplayback" in href):
                            final_link = href
                            logger.info(f"Found direct link from attribute: {final_link}")
                            break # Found link

                        # OPTION B: Click element to reveal link or go to new page
                        logger.info(f"Clicking element for {server_pref['name']}...")
                        
                        # Handle potential new tab opened by click
                        async with context.expect_page(timeout=15000) if "vcloud" not in page.url.lower() else page: # Heuristic for external vcloud
                            await server_element_locator.click(timeout=10000, force=True) # force=True can help with overlaid elements

                        # If new page opened, switch to it
                        if len(context.pages) > 1 and context.pages[-1] != page:
                            new_page = context.pages[-1]
                            await new_page.bring_to_front()
                            current_page_for_link_search = new_page
                            logger.info(f"Switched to new page: {current_page_for_link_search.url}")
                        else:
                            current_page_for_link_search = page # Stay on current page
                        
                        await current_page_for_link_search.wait_for_load_state('domcontentloaded', timeout=20000)
                        await current_page_for_link_search.wait_for_timeout(5000) # Give time for JS

                        # Now, on the current/new page, search for the final link
                        # 1. Direct .mp4/.mkv link in URL
                        if current_page_for_link_search.url.endswith((".mp4", ".mkv", ".avi")) or "googlevideo.com/videoplayback" in current_page_for_link_search.url:
                            final_link = current_page_for_link_search.url
                            logger.info(f"Page URL is direct link: {final_link}")
                            break
                        
                        # 2. Video tag src
                        video_element = current_page_for_link_search.locator("video[src]").first
                        if await video_element.count() > 0 and await video_element.is_visible(timeout=3000):
                            src = await video_element.get_attribute("src")
                            if src and (src.endswith((".mp4", ".mkv")) or "googlevideo.com/videoplayback" in src):
                                final_link = src
                                logger.info(f"Found video src link: {final_link}")
                                break
                        
                        # 3. Download button with a direct link
                        download_button = current_page_for_link_search.locator(
                            'a[download][href*=".mp4"], a[download][href*=".mkv"], '
                            'a[href*=".mp4"]:has-text(/download/i), a[href*=".mkv"]:has-text(/download/i), '
                            'button:has-text(/download/i)' # This might need another click
                        ).first
                        if await download_button.count() > 0 and await download_button.is_visible(timeout=3000):
                            href = await download_button.get_attribute("href")
                            if href and (href.endswith((".mp4", ".mkv")) or "googlevideo.com/videoplayback" in href):
                                 final_link = href
                                 logger.info(f"Found direct download button link: {final_link}")
                                 break
                            # If it's a button that needs another click, this logic would need extension
                        
                        if final_link: break # Found link
                    if final_link: break
                except PlaywrightTimeoutError:
                    logger.debug(f"Timeout finding/interacting with {server_pref['name']} using '{identifier}'")
                except Exception as find_click_ex:
                    logger.warning(f"Could not find/interact with {server_pref['name']} using '{identifier}': {find_click_ex}")
            if final_link: break # Found link, exit server priority loop
        
        # DUMMY LINK if all else fails for placeholder (REPLACE THIS)
        if not final_link and ("dummy-movie-site" in source_site or "example.com" in source_site): # Check if it's a known dummy site
            await asyncio.sleep(0.1)
            final_link = f"{download_trigger_url}/final_vcloud_link_server1_dummy.mp4"
            logger.warning(f"Using DUMMY final link: {final_link}")
        # --- END OF DUMMY VCLOUD LOGIC ---

    except PlaywrightTimeoutError as pte:
        logger.error(f"Timeout getting final VCloud link from {download_trigger_url}: {pte}")
    except Exception as e:
        logger.error(f"Error getting final VCloud link from {download_trigger_url}: {e}", exc_info=True)
    finally:
        if browser: await close_playwright_resources(browser, context, playwright_instance_provided=False if playwright else True)
        if playwright and not browser: await playwright.stop()
    
    if final_link:
        logger.info(f"Final VCloud download link: {final_link}")
    else:
        logger.warning(f"Could not retrieve a VCloud download link from {download_trigger_url}")
    return final_link