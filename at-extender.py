# -*- coding: utf-8 -*-
import json
import time
import requests
import logging
import random
import os
import sys
import io
import re
try:
    import psutil
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
    import psutil
from playwright.sync_api import sync_playwright, TimeoutError

def is_low_memory():
    #Erkennt schwache Server (unter 2 GB RAM)
    total_ram = psutil.virtual_memory().total / (1024**3)
    return total_ram <= 2.0

def get_launch_args(browser):
    if browser == "chromium" and is_low_memory():
        return ["--no-sandbox", "--disable-dev-shm-usage"]
    else:
        return []



# Logging einrichten
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

LOGIN_URL = "https://login.alditalk-kundenbetreuung.de/signin/XUI/#login/"
DASHBOARD_URL = "https://www.alditalk-kundenportal.de/portal/auth/uebersicht/"

VERSION = "1.2.1"  # Deine aktuelle Version

REMOTE_VERSION_URL = "https://raw.githubusercontent.com/Dinobeiser/AT-Extender/main/version.txt"  # Link zur Version
REMOTE_SCRIPT_URL = "https://raw.githubusercontent.com/Dinobeiser/AT-Extender/main/at-extender.py"  # Link zum neuesten Skript

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/139.0"
HEADLESS = True
browser = None

def load_config():
    with open("config.json", "r") as f:
        config = json.load(f)

    valid_browsers = ["chromium", "firefox", "webkit"]
    browser = config.get("BROWSER", "chromium").lower()

    if browser not in valid_browsers:
        logging.warning(f"Ungültiger Browserwert '{browser}' in config.json - fallback auf 'chromium'")
        browser = "chromium"

    config["BROWSER"] = browser
    return config


config = load_config()

RUFNUMMER = config["RUFNUMMER"]
PASSWORT = config["PASSWORT"]
BOT_TOKEN = config["BOT_TOKEN"]
CHAT_ID = config["CHAT_ID"]
AUTO_UPDATE = config["AUTO_UPDATE"]
TELEGRAM = config["TELEGRAM"]
DISCORD = config["DISCORD"]
DISCORD_WEBHOOK = config.get("DISCORD_WEBHOOK", "")
SLEEP_MODE = config["SLEEP_MODE"]
SLEEP_INTERVAL = config["SLEEP_INTERVAL"]
BROWSER = config["BROWSER"]
INFO_LEVEL = int(config["INFO_LEVEL"])

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

LAST_GB = 0.0

try:
    with open("state.json", "r") as f:
        data = json.load(f)
        if isinstance(data, dict) and "last_gb" in data:
            LAST_GB = float(data["last_gb"])
        else:
            raise ValueError("Ungültiges Format in state.json - setze zurück.")
except Exception as e:
    try:
        with open("state.json", "w") as f:
            json.dump({"last_gb": 0.0}, f)
    except Exception as save_error:
        logging.error(f"Konnte 'state.json' nicht neu erstellen: {save_error}")

def sendMessage(type, message):
    if TELEGRAM == "1":
        if type == "info" and INFO_LEVEL == 1 and INFO_LEVEL != 3 and INFO_LEVEL != 2:
            send_telegram_message(message)
            send_discord_message(message, type)
        elif type == "warn" and INFO_LEVEL >= 1 and INFO_LEVEL != 3:
            send_telegram_message(message)
            send_discord_message(message, type)
        elif type == "error" and INFO_LEVEL >= 1:
            send_telegram_message(message)
            send_discord_message(message, type)
        elif type != "info" and type != "warn" and type != "error":
            logging.error(f"Unbekannter Typ '{type}' oder INFO_LEVEL zu niedrig: {message}")
            send_telegram_message(f"Unbekannter Typ '{type}' oder INFO_LEVEL zu niedrig: {message}")
            send_discord_message(f"Unbekannter Typ '{type}' oder INFO_LEVEL zu niedrig: {message}", "error")

def send_telegram_message(message, retries=3):
    if TELEGRAM == "1":
        for attempt in range(retries):
            try:
                response = requests.post(TELEGRAM_URL, data={"chat_id": CHAT_ID, "text": message})
                if response.status_code == 200:
                    logging.info("Telegram-Nachricht erfolgreich gesendet.")
                    return True
                else:
                    logging.warning(f"Fehler beim Senden (Versuch {attempt+1}): {response.text}")
            except Exception as e:
                logging.error(f"Fehler beim Telegram-Senden (Versuch {attempt+1}): {e}")
        logging.error("Telegram konnte nicht erreicht werden.")
        return False
    else:
        print("Keine Telegram Notify erwünscht")

def send_discord_message(message, type, retries=3):
    if DISCORD == "1":
        color_map = {
            "info": 3447003,    # Blau
            "warn": 16776960,   # Gelb
            "error": 15158332   # Rot
        }
        embed_color = color_map.get(type, 15158332)
        embed = {
            "description": message,
            "color": embed_color
        }
        payload = {
            "embeds": [embed]
        }
        for attempt in range(retries):
            try:
                if DISCORD_WEBHOOK:
                    response = requests.post(DISCORD_WEBHOOK, json=payload)
                    if response.status_code == 204:
                        logging.info("Discord-Nachricht erfolgreich gesendet.")
                        return True
                    else:
                        logging.warning(f"Fehler beim Senden (Versuch {attempt+1}): {response.text}")
                else:
                    logging.error("Discord Webhook URL ist nicht gesetzt.")
            except Exception as e:
                logging.error(f"Fehler beim Discord-Senden (Versuch {attempt+1}): {e}")
        logging.error("Discord konnte nicht erreicht werden.")
        return False
    else:
        print("Keine Discord Notify erwünscht")


# Funktion, um Versionen zu vergleichen (Versionen in Tupel umwandeln)
def compare_versions(local, remote):
    def to_tuple(v): return tuple(map(int, v.strip().split(".")))
    return to_tuple(remote) > to_tuple(local)

# Funktion, die auf Updates prüft
def check_for_update():
    if AUTO_UPDATE == "1":
        try:
            logging.info("🔍 Prüfe auf Updates...")

            response = requests.get(REMOTE_VERSION_URL)
            if response.status_code != 200:
                print(f"⚠️  Konnte Versionsinfo nicht abrufen, Statuscode: {response.status_code}")
                return

            remote_version = response.text.strip()
            logging.info(f"🔍 Lokale Version: {VERSION} | Remote Version: {remote_version}")

            if compare_versions(VERSION, remote_version):
                logging.info(f"🚀 Neue Version verfügbar: {remote_version} (aktuell: {VERSION})")
                update = requests.get(REMOTE_SCRIPT_URL)
                if update.status_code == 200:
                    logging.info("✅ Update wird heruntergeladen...")
                    script_path = os.path.realpath(sys.argv[0])
                    with open(script_path, 'w', encoding='utf-8') as f:
                        f.write(update.text)
                    logging.info("✅ Update erfolgreich! Starte neu...")

                    # Universeller Neustart - funktioniert mit venv & system-python
                    os.execv(sys.executable, [sys.executable] + sys.argv)

                else:
                    logging.info(f"❌ Fehler beim Herunterladen der neuen Version, Statuscode: {update.status_code}")
            else:
                logging.info("✅ Du verwendest die neueste Version.")
        except Exception as e:
            logging.info(f"❌ Fehler beim Update-Check: {e}")
    else:
        logging.info(f"Kein AutoUpdate erwünscht.")

def wait_and_click(page, selector, timeout=5000, retries=5):
    for attempt in range(retries):
        try:
            logging.info(f"Versuche, auf {selector} zu klicken (Versuch {attempt+1}/{retries})...")
            page.wait_for_selector(selector, timeout=timeout)
            page.click(selector)
            return True
        except TimeoutError:
            logging.warning(f"{selector} nicht gefunden. Neuer Versuch...")
            time.sleep(1)
    logging.error(f"Konnte {selector} nicht klicken.")
    return False

def handle_cookie_banner(page):
    try:
        cookie_selector = 'button[data-testid="uc-deny-all-button"]'
        if page.query_selector(cookie_selector):
            logging.info("Achtung vor dem Krümelmonster.")
            wait_and_click(page, cookie_selector)
            logging.info("Nom Nom Nom")
    except Exception as e:
        logging.warning(f"Cookie Fenster nicht klickbar: {e}")


def get_datenvolumen(page):
    logging.info("Lese Datenvolumen aus...")

    try:
        label_selectors = [
            'one-stack.usage-meter:nth-child(1) > one-usage-meter:nth-child(1) > one-button:nth-child(2)',
            'one-stack.usage-meter:nth-child(1) > one-stack:nth-child(1) > one-usage-meter:nth-child(1) > one-button:nth-child(2)'
        ]

        label_text = ""
        is_community_plus = False

        for sel in label_selectors:
            try:
                element = page.query_selector(sel)
                if element:
                    label_text = element.text_content().strip()
                    if label_text:
                        break
            except Exception as e:
                logging.warning(f"Selector {sel} für Community+ Label nicht gefunden: {e}")

        if "Inland & EU" in label_text:
            is_community_plus = True
            logging.info("Community+ erkannt")
            GB_selectors = [
                'one-stack.usage-meter:nth-child(2) > one-usage-meter:nth-child(1) > one-group:nth-child(1) > one-heading:nth-child(2)',
                'one-stack.usage-meter:nth-child(2) > one-stack:nth-child(1) > one-usage-meter:nth-child(1) > one-group:nth-child(1) > one-heading:nth-child(2)'
            ]
        else:
            logging.info("Kein Community+ erkannt")
            GB_selectors = [
                'one-stack.usage-meter:nth-child(1) > one-usage-meter:nth-child(1) > one-group:nth-child(1) > one-heading:nth-child(2)',
                'one-stack.usage-meter:nth-child(1) > one-stack:nth-child(1) > one-usage-meter:nth-child(1) > one-group:nth-child(1) > one-heading:nth-child(2)'
            ]
    except Exception as e:
        logging.warning(f"Fehler bei der Erkennung von Community+: {e}")
        is_community_plus = False  # Fallback
        GB_selectors = [
            'one-stack.usage-meter:nth-child(1) > one-usage-meter:nth-child(1) > one-group:nth-child(1) > one-heading:nth-child(2)',
            'one-stack.usage-meter:nth-child(1) > one-stack:nth-child(1) > one-usage-meter:nth-child(1) > one-group:nth-child(1) > one-heading:nth-child(2)'
        ]


    GB_text_raw = None
    for sel in GB_selectors:
        try:
            element = page.query_selector(sel)
            if element:
                GB_text_raw = element.text_content()
                if GB_text_raw:
                    break
        except Exception as e:
            logging.warning(f"Selector {sel} nicht verfügbar: {e}")
            continue

    if not GB_text_raw:
        raise Exception("Konnte das Datenvolumen nicht auslesen - kein gültiger Selector gefunden.")

    match = re.search(r"([\d\.,]+)\s?(GB|MB)", GB_text_raw)
    if not match:
        raise ValueError(f"Unerwartetes Format beim Datenvolumen: {GB_text_raw}")

    value, unit = match.groups()
    value = value.replace(",", ".")

    if unit == "MB":
        GB = float(value) / 1024
    else:
        GB = float(value)

    return GB, is_community_plus


def login_and_check_data():
    global LAST_GB
    with sync_playwright() as p:
        for attempt in range(3):  # 3 Versuche, falls Playwright abstürzt
            try:
                COOKIE_FILE = "cookies.json"
                logging.info(f"Starte {BROWSER}...")
                LAUNCH_ARGS = get_launch_args(BROWSER)

                # Browser starten
                if BROWSER == "firefox":
                    browser = p.firefox.launch(headless=HEADLESS, args=LAUNCH_ARGS)
                elif BROWSER == "webkit":
                    browser = p.webkit.launch(headless=HEADLESS, args=LAUNCH_ARGS)
                else:
                    browser = p.chromium.launch(headless=HEADLESS, args=LAUNCH_ARGS)

                # Cookies vorbereiten
                if os.path.exists(COOKIE_FILE):
                    logging.info("Lade gespeicherte Cookies...")
                    context = browser.new_context(user_agent=USER_AGENT, storage_state=COOKIE_FILE)
                else:
                    logging.info("Keine Cookies vorhanden - neuer Kontext wird erstellt.")
                    context = browser.new_context(user_agent=USER_AGENT)

                page = context.new_page()

                # Hilfsfunktion: prüfen, ob eingeloggt anhand Überschrift
                def login_erfolgreich(p):
                    try:
                        p.wait_for_selector('one-heading[level="h1"]', timeout=8000)
                        heading = p.text_content('one-heading[level="h1"]')
                        return heading and "Übersicht" in heading
                    except:
                        return False

                # Dashboard aufrufen
                page.goto(DASHBOARD_URL, wait_until="domcontentloaded")
                time.sleep(3)
                handle_cookie_banner(page)

                # Prüfen ob auf Login-Seite umgeleitet wurde
                if "login" in page.url:
                    logging.info("Nicht eingeloggt - Login wird durchgeführt...")
                    page.goto(LOGIN_URL)
                    page.wait_for_load_state("domcontentloaded")
                    handle_cookie_banner(page)

                    logging.info("Fülle Login-Daten aus...")
                    page.fill('#input-5', RUFNUMMER)
                    page.fill('#input-6', PASSWORT)

                    if not wait_and_click(page, '[class="button button--solid button--medium button--color-default button--has-label"]'):
                        raise Exception("Login-Button konnte nicht geklickt werden.")

                    logging.info("Warte auf Login...")
                    time.sleep(8)
                    page.wait_for_load_state("domcontentloaded")
                    handle_cookie_banner(page)

                    if login_erfolgreich(page):
                        logging.info("Login erfolgreich - Cookies werden gespeichert.")
                        context.storage_state(path=COOKIE_FILE)
                    else:
                        raise Exception("Login fehlgeschlagen - Übersichtsseite nicht sichtbar.")
                else:
                    logging.info(" Bereits eingeloggt - Zugriff aufs Dashboard funktioniert.")

                    if not login_erfolgreich(page):
                        logging.warning("Session scheint abgelaufen oder inkonsistent - versuche erneuten Login...")

                        if os.path.exists(COOKIE_FILE):
                            os.remove(COOKIE_FILE)
                            logging.info("Alte Cookies wurden gelöscht, da ungültig.")

                        # Versuche Login erneut
                        page.goto(LOGIN_URL)
                        page.wait_for_load_state("domcontentloaded")
                        handle_cookie_banner(page)

                        logging.info("Fülle Login-Daten aus (Fallback)...")
                        page.fill('#input-5', RUFNUMMER)
                        page.fill('#input-6', PASSWORT)

                        if not wait_and_click(page, '[class="button button--solid button--medium button--color-default button--has-label"]'):
                            raise Exception("Fallback-Login: Login-Button konnte nicht geklickt werden.")

                        logging.info("Warte auf Login... (Fallback)")
                        time.sleep(8)
                        page.wait_for_load_state("domcontentloaded")
                        handle_cookie_banner(page)

                        if login_erfolgreich(page):
                            logging.info("Fallback-Login erfolgreich neue Cookies werden gespeichert.")
                            context.storage_state(path=COOKIE_FILE)
                        else:
                            raise Exception("Fallback-Login fehlgeschlagen Session kann nicht wiederhergestellt werden.")

                    # Session aktiv verlängern durch Aktion:
                    try:
                        page.hover('one-heading[level="h1"]')
                        logging.info("Session-Aktivität erfolgreich simuliert hover auf Überschrift.")
                    except:
                        logging.warning("Session konnte nicht ausgeführt werden.")

                    #
                    logging.info("Cookies werden erneuert.")
                    context.storage_state(path=COOKIE_FILE)

                GB, is_community_plus = get_datenvolumen(page)
                LAST_GB = GB

                try:
                    with open("state.json", "w") as f:
                        json.dump({"last_gb": LAST_GB}, f)
                except Exception as e:
                    logging.warning(f"Fehler beim Speichern des GB-Werts: {e}")

                interval = get_interval(config)


                if GB < 1.0:
                    logging.info("Versuche, 1 GB Datenvolumen nachzubuchen...")

                    if is_community_plus:
                        selectors = [
                            'one-stack.usage-meter:nth-child(2) > one-usage-meter:nth-child(1) > one-button:nth-child(3)',
                            'one-stack.usage-meter:nth-child(2) > one-stack:nth-child(1) > one-usage-meter:nth-child(1) > one-button:nth-child(3)'
                        ]
                    else:
                        selectors = [
                            'one-stack.usage-meter:nth-child(1) > one-usage-meter:nth-child(1) > one-button:nth-child(3)',
                            'one-stack.usage-meter:nth-child(1) > one-stack:nth-child(1) > one-usage-meter:nth-child(1) > one-button:nth-child(3)'
                        ]

                    clicked = False
                    for selector in selectors:
                        try:
                            button = page.query_selector(selector)
                            if button and "1 GB" in button.text_content():
                                if wait_and_click(page, selector):
                                    logging.info(f"Nachbuchungsbutton geklickt über Selector: {selector}")
                                    message = f"{RUFNUMMER}: Aktuelles Datenvolumen: {GB:.2f} GB - 1 GB wurde erfolgreich nachgebucht. 📲"
                                    sendMessage("info", message)
                                    clicked = True
                                    break
                        except Exception as e:
                            logging.warning(f"❌ Fehler beim Versuch mit Selector {selector}: {e}")

                    if is_community_plus:
                        selectors = [
                            'one-stack.usage-meter:nth-child(2) > one-usage-meter:nth-child(1) > one-button:nth-child(3)',
                            'one-stack.usage-meter:nth-child(2) > one-stack:nth-child(1) > one-usage-meter:nth-child(1) > one-button:nth-child(3)'
                        ]
                    else:
                        selectors = [
                            'one-stack.usage-meter:nth-child(1) > one-usage-meter:nth-child(1) > one-button:nth-child(3)',
                            'one-stack.usage-meter:nth-child(1) > one-stack:nth-child(1) > one-usage-meter:nth-child(1) > one-button:nth-child(3)'
                        ]

                    clicked = False
                    for selector in selectors:
                        try:
                            button = page.query_selector(selector)
                            if button and "1 GB" in button.text_content():
                                if wait_and_click(page, selector):
                                    logging.info(f"Nachbuchungsbutton geklickt über Selector: {selector}")
                                    message = f"{RUFNUMMER}: Aktuelles Datenvolumen: {GB:.2f} GB - 1 GB wurde erfolgreich nachgebucht. 📲"
                                    sendMessage(message, "info")
                                    clicked = True
                                    break
                        except Exception as e:
                            logging.warning(f"❌ Fehler beim Versuch mit Selector {selector}: {e}")

                    if not clicked:
                        raise Exception("❌ Kein gültiger 1 GB-Button gefunden oder kein Klick möglich.")
                    interval = get_interval(config)
                    return interval

                else:
                    logging.info(f"Aktuelles Datenvolumen: {GB:.2f} GB")
                    sendMessage("info", f"{RUFNUMMER}: Noch {GB:.2f} GB übrig. Nächster Run in {interval} Sekunden. ✅")


                return get_interval(config)
            except Exception as e:
                logging.error(f"Fehler im Versuch {attempt+1}: {e}")
                sendMessage(f"{RUFNUMMER}: ❌ Fehler beim Abrufen des Datenvolumens: {e}", "error")

            finally:
                if browser:
                    browser.close()
                    logging.info("Browser geschlossen.")

            time.sleep(2)
        logging.error("Skript hat nach 3 Versuchen aufgegeben.")


def get_smart_interval():
    if LAST_GB >= 10:
        return random.randint(3600, 5400)
    elif LAST_GB >= 5:
        return random.randint(900, 1800)
    elif LAST_GB >= 3:
        return random.randint(600, 900)
    elif LAST_GB >= 2:
        return random.randint(300, 450)
    elif LAST_GB >= 1.2:
        return random.randint(150, 240)
    elif LAST_GB >= 1.0:
        return random.randint(60, 90)
    else:
        return 60  # Fallback


def get_interval(config):
    mode = config.get("SLEEP_MODE", "random")
    if mode == "smart":
        return get_smart_interval()
    elif mode == "fixed":
        try:
            return int(config.get("SLEEP_INTERVAL", 90))
        except ValueError:
            return 90
    elif mode.startswith("random_"):
        try:
            _, range_str = mode.split("_", 1)
            min_val, max_val = map(int, range_str.split("-"))

            if min_val >= max_val:
                raise ValueError("Min muss kleiner als Max sein")
            return random.randint(min_val, max_val)

        except Exception as e:
            return random.randint(300, 500)

    else:
        return random.randint(300, 500)


if __name__ == "__main__":
    while True:
        check_for_update()
        logging.info("Starte neuen Durchlauf...")
        interval = login_and_check_data()
        logging.info(f"💤 Warte {interval} Sekunden...")
        time.sleep(interval)
