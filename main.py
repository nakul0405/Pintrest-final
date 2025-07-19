import os
import json
import time
import telebot
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from threading import Thread

# Load environment variables (Zeabur: use panel, no .env)
EMAIL = os.environ["PINTEREST_EMAIL"]
PASSWORD = os.environ["PINTEREST_PASSWORD"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

bot = telebot.TeleBot(BOT_TOKEN)

# Track multiple profiles (saved in a local file)
TRACK_FILE = "tracked_profiles.json"
PIN_DB_FILE = "old_pins.json"

# Load tracked profiles
def load_profiles():
    try:
        with open(TRACK_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

# Save updated profile list
def save_profiles(profiles):
    with open(TRACK_FILE, 'w') as f:
        json.dump(profiles, f)

# Load already seen pins
def load_old_pins():
    try:
        with open(PIN_DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

# Save updated pin db
def save_old_pins(data):
    with open(PIN_DB_FILE, "w") as f:
        json.dump(data, f)

# Login + scrape saved pins
def scrape_saved_pins(username):
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)

    try:
        print(f"🔐 Logging in to Pinterest for scraping {username}...")
# ✅ Load cookies if available
if os.path.exists("cookies.json"):
    driver.get("https://www.pinterest.com/")  # Open base URL first
    with open("cookies.json", "r") as f:
        cookies = json.load(f)
    for cookie in cookies:
        if "sameSite" in cookie:  # Pinterest may not accept that
            del cookie["sameSite"]
        driver.add_cookie(cookie)
    driver.refresh()
    time.sleep(3)
        driver.get("https://www.pinterest.com/login")
        time.sleep(4)
# Check if already logged in
if "Log in" not in driver.page_source and "password" not in driver.page_source:
    print("✅ Already logged in via cookies.")
else:
    print(f"🔐 Logging in to Pinterest for scraping {username}...")
    driver.get("https://www.pinterest.com/login")
    time.sleep(4)
    driver.find_element(By.NAME, "id").send_keys(EMAIL)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(6)

    # ✅ Save cookies after fresh login
    with open("cookies.json", "w") as f:
        json.dump(driver.get_cookies(), f)
        
        driver.find_element(By.NAME, "id").send_keys(EMAIL)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(6)

        driver.get(f"https://www.pinterest.com/{username}/_saved")
        time.sleep(5)

        # ✅ Save cookies after login
        with open("cookies.json", "w") as f:
            json.dump(driver.get_cookies(), f)
            
        # Scroll and re-grab elements AFTER scroll to avoid stale error
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

        # 💡 Freshly grab elements AFTER scroll
        print("🔍 Extracting fresh pins from DOM...")
        pins = driver.find_elements(By.XPATH, '//a[contains(@href, "/pin/")]')

        pin_links = []
        for p in pins:
            try:
                href = p.get_attribute("href")
                if href and "/pin/" in href:
                    full_link = "https://www.pinterest.com" + href if href.startswith("/") else href
                    pin_links.append(full_link)
            except Exception as e:
                print(f"⚠️ Skipping stale pin: {e}")

        return list(set(pin_links))

    except Exception as e:
        print(f"❌ Error scraping {username}: {e}")
        return []
    finally:
        driver.quit()

# Check for new pins and notify
def check_all_profiles():
    tracked = load_profiles()
    old_data = load_old_pins()

    for username in tracked:
        print(f"🔍 Checking pins for: {username}")
        pins = scrape_saved_pins(username)

        if username not in old_data:
            old_data[username] = pins
            continue

        new_pins = [p for p in pins if p not in old_data[username]]
        if new_pins:
            for pin in new_pins:
                bot.send_message(CHAT_ID, f"🆕 New pin by {username}:\n{pin}")
            old_data[username].extend(new_pins)

    save_old_pins(old_data)

# Telegram command: /start
@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.reply_to(message, "👋 Bot is live! Use /track <pinterest_profile_url> to track saved pins.")

# Telegram command: /track <url>
@bot.message_handler(commands=['track'])
def track_handler(message):
    text = message.text.strip()
    parts = text.split()

    if len(parts) != 2 or "pinterest.com" not in parts[1]:
        bot.reply_to(message, "❌ Invalid format. Use: /track https://www.pinterest.com/username/_saved")
        return

    # Extract username from URL
    url = parts[1]
    try:
        username = url.split("pinterest.com/")[1].split("/")[0]
    except:
        bot.reply_to(message, "❌ Couldn't extract username. Check the URL.")
        return

    tracked = load_profiles()
    if username in tracked:
        bot.reply_to(message, f"✅ Already tracking `{username}`.")
        return

    tracked.append(username)
    save_profiles(tracked)
    bot.reply_to(message, f"📌 Now tracking `{username}` for new saved pins.")

# Background thread for periodic checking
def start_polling_loop():
    while True:
        print("⏰ Running scheduled check...")
        check_all_profiles()
        time.sleep(90)  # Every 15 minutes

# Start background thread
Thread(target=start_polling_loop, daemon=True).start()

# Start bot command polling
print("🤖 Bot is now live.")
bot.polling()
