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
    # options.add_argument("--headless")  # ❌ Hata diya to debug visually
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)

    try:
        print(f"🔐 Logging in to Pinterest for scraping {username}...")

        # 🧹 Remove old cookies if exist (to force fresh login)
        if os.path.exists("cookies.json"):
            try:
                os.remove("cookies.json")
                print("🧹 Old cookies removed.")
            except Exception as e:
                print("⚠️ Couldn't delete cookies:", e)

        # ✅ Load cookies if available
        if os.path.exists("cookies.json"):
            driver.get("https://www.pinterest.com/")
            with open("cookies.json", "r") as f:
                cookies = json.load(f)
            for cookie in cookies:
                if "sameSite" in cookie:
                    del cookie["sameSite"]
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    print("⚠️ Cookie issue:", e)
            driver.refresh()
            time.sleep(3)

        driver.get("https://www.pinterest.com/login")
        time.sleep(4)

        # Check if already logged in
        if "Log in" not in driver.page_source and "password" not in driver.page_source:
            print("✅ Already logged in via cookies.")
        else:
            print("🔁 Performing fresh login...")
            driver.get("https://www.pinterest.com/login")
            time.sleep(4)

            try:
                driver.find_element(By.NAME, "id").send_keys(EMAIL)
                driver.find_element(By.NAME, "password").send_keys(PASSWORD)
            except Exception as e:
                print(f"❌ Login input fields not found: {e}")
                driver.quit()
                return []

            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(6)

            with open("cookies.json", "w") as f:
                json.dump(driver.get_cookies(), f)

        driver.get(f"https://www.pinterest.com/{username}/_saved")
        time.sleep(5)

        with open("cookies.json", "w") as f:
            json.dump(driver.get_cookies(), f)

        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

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
        time.sleep(90)

Thread(target=start_polling_loop, daemon=True).start()

print("🤖 Bot is now live.")
bot.polling()
