import os
import json
import time
import telebot
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# Load from Zeabur environment variables
EMAIL = os.environ["PINTEREST_EMAIL"]
PASSWORD = os.environ["PINTEREST_PASSWORD"]
USERNAME = os.environ["PINTEREST_USERNAME"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

bot = telebot.TeleBot(BOT_TOKEN)

def load_old_pins():
    try:
        with open("old_pins.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_pins(pins):
    with open("old_pins.json", "w") as f:
        json.dump(pins, f)

def login_and_scrape():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)

    print("🔐 Logging into Pinterest...")
    driver.get("https://www.pinterest.com/login")
    time.sleep(4)

    driver.find_element(By.NAME, "id").send_keys(EMAIL)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(6)

    print("📥 Opening /saved tab...")
    driver.get(f"https://www.pinterest.com/{USERNAME}/_saved")
    time.sleep(6)

    # Optional: scroll to load more pins
    for _ in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

    print("🔍 Scraping pin URLs...")
    pins = driver.find_elements(By.XPATH, '//a[contains(@href, "/pin/")]')
    pin_links = list(set(["https://www.pinterest.com" + p.get_attribute("href") for p in pins]))

    driver.quit()
    return pin_links

def check_and_notify():
    current_pins = login_and_scrape()
    old_pins = load_old_pins()
    new_pins = [p for p in current_pins if p not in old_pins]

    if new_pins:
        print(f"🆕 Found {len(new_pins)} new pins.")
        for pin in new_pins:
            bot.send_message(CHAT_ID, f"🆕 New pin saved:\n{pin}")
        save_pins(current_pins)
    else:
        print("📭 No new pins found.")

# Run once
check_and_notify()

# Optional: Continuous polling every 15 minutes
# while True:
#     check_and_notify()
#     time.sleep(900)  # 15 min
