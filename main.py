import os
import json
import time
import telebot
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from threading import Thread
import requests

EMAIL = os.environ["PINTEREST_EMAIL"]
PASSWORD = os.environ["PINTEREST_PASSWORD"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

bot = telebot.TeleBot(BOT_TOKEN)

TRACK_FILE = "tracked_profiles.json"
PIN_DB_FILE = "old_pins.json"

def load_profiles():
    try:
        with open(TRACK_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_profiles(profiles):
    with open(TRACK_FILE, 'w') as f:
        json.dump(profiles, f)

def load_old_pins():
    try:
        with open(PIN_DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_old_pins(data):
    with open(PIN_DB_FILE, "w") as f:
        json.dump(data, f)

def extract_image_url(pin_url):
    try:
        res = requests.get(pin_url)
        if "og:image" in res.text:
            return res.text.split('property="og:image"')[1].split('content="')[1].split('"')[0]
    except:
        return None

def scrape_saved_pins(username):
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)

    try:
        print(f"🔐 Logging in to Pinterest for scraping {username}...")

        driver.get("https://www.pinterest.com/")
        time.sleep(2)

        if os.path.exists("cookies.json"):
            with open("cookies.json", "r") as f:
                cookies = json.load(f)
            for cookie in cookies:
                cookie.pop("sameSite", None)
                cookie.pop("domain", None)
                try:
                    driver.add_cookie(cookie)
                except:
                    pass
            driver.refresh()
            time.sleep(2)

        driver.get("https://www.pinterest.com/login")
        time.sleep(3)

        if "Log in" in driver.page_source or "password" in driver.page_source:
            print("🔁 Performing fresh login...")
            driver.find_element(By.CSS_SELECTOR, 'input[type="email"]').send_keys(EMAIL)
            driver.find_element(By.NAME, "password").send_keys(PASSWORD)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(6)
            with open("cookies.json", "w") as f:
                json.dump(driver.get_cookies(), f)
        else:
            print("✅ Logged in using cookies.")

        driver.get(f"https://www.pinterest.com/{username}/_saved")
        time.sleep(5)

        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        pins = driver.find_elements(By.XPATH, '//a[contains(@href, "/pin/")]')
        pin_links = []
        for p in pins:
            try:
                href = p.get_attribute("href")
                if href and "/pin/" in href:
                    full_link = "https://www.pinterest.com" + href if href.startswith("/") else href
                    pin_links.append(full_link)
            except:
                continue

        return list(set(pin_links))

    except Exception as e:
        print(f"❌ Error scraping {username}: {e}")
        return []
    finally:
        driver.quit()

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
                img = extract_image_url(pin)
                if img:
                    bot.send_photo(CHAT_ID, img, caption=f"🆕 New pin by {username}:\n{pin}")
                else:
                    bot.send_message(CHAT_ID, f"🆕 New pin by {username}:\n{pin}")
            old_data[username].extend(new_pins)

    save_old_pins(old_data)

@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.reply_to(message, "👋 Bot is live! Use /track <pinterest_profile_url> to track saved pins.")

@bot.message_handler(commands=['track'])
def track_handler(message):
    text = message.text.strip()
    parts = text.split()

    if len(parts) != 2 or "pinterest.com" not in parts[1]:
        bot.reply_to(message, "❌ Invalid format. Use: /track https://www.pinterest.com/username/_saved")
        return

    try:
        username = parts[1].split("pinterest.com/")[1].split("/")[0]
    except:
        bot.reply_to(message, "❌ Couldn't extract username.")
        return

    tracked = load_profiles()
    if username in tracked:
        bot.reply_to(message, f"✅ Already tracking `{username}`.")
        return

    tracked.append(username)
    save_profiles(tracked)
    bot.reply_to(message, f"📌 Now tracking `{username}`.")

@bot.message_handler(commands=['status'])
def status_handler(message):
    tracked = load_profiles()
    if not tracked:
        bot.reply_to(message, "⚠️ No profiles are currently being tracked.")
    else:
        msg = "📊 Currently tracking:\n" + "\n".join(f"• {u}" for u in tracked)
        bot.reply_to(message, msg)

@bot.message_handler(commands=['stop'])
def stop_handler(message):
    parts = message.text.strip().split()
    if len(parts) != 2:
        bot.reply_to(message, "❌ Use: /stop username")
        return

    username = parts[1]
    tracked = load_profiles()
    if username not in tracked:
        bot.reply_to(message, f"⚠️ `{username}` is not being tracked.")
        return

    tracked.remove(username)
    save_profiles(tracked)
    bot.reply_to(message, f"🛑 Stopped tracking `{username}`.")

def start_polling_loop():
    while True:
        print("⏰ Running scheduled check...")
        check_all_profiles()
        time.sleep(300)

Thread(target=start_polling_loop, daemon=True).start()
print("🤖 Bot is now live.")
bot.polling()
