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

VERSION = "1.2.3"  # Deine aktuelle Version

REMOTE_VERSION_URL = "https://raw.githubusercontent.com/Dinobeiser/AT-Extender/main/version.txt"  # Link zur Version
REMOTE_SCRIPT_URL = "https://raw.githubusercontent.com/Dinobeiser/AT-Extender/main/at-extender.py"  # Link zum neuesten Skript

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/139.0"
HEADLESS = True
browser = None

def load_config():
    # First, try to load from environment variables (Docker support)
    config = {
        "RUFNUMMER": os.getenv("RUFNUMMER"),
        "PASSWORT": os.getenv("PASSWORT"),
        "TELEGRAM": os.getenv("TELEGRAM"),
        "BOT_TOKEN": os.getenv("BOT_TOKEN"),
        "CHAT_ID": os.getenv("CHAT_ID"),
        "AUTO_UPDATE": os.getenv("AUTO_UPDATE"),
        "SLEEP_MODE": os.getenv("SLEEP_MODE"),
        "SLEEP_INTERVAL": os.getenv("SLEEP_INTERVAL"),
        "BROWSER": os.getenv("BROWSER")
    }
    
    # Check if we have the required environment variables
    if config["RUFNUMMER"] and config["PASSWORT"]:
        logging.info("Verwende Konfiguration aus Umgebungsvariablen")
        # Set defaults for optional values
        config["TELEGRAM"] = config["TELEGRAM"] or "0"
        config["BOT_TOKEN"] = config["BOT_TOKEN"] or ""
        config["CHAT_ID"] = config["CHAT_ID"] or ""
        config["AUTO_UPDATE"] = config["AUTO_UPDATE"] or "1"
        config["SLEEP_MODE"] = config["SLEEP_MODE"] or "smart"
        config["SLEEP_INTERVAL"] = config["SLEEP_INTERVAL"] or "70"
        config["BROWSER"] = config["BROWSER"] or "chromium"
    else:
        # Try to load from Docker secrets
        secrets_config = load_docker_secrets()
        if secrets_config:
            logging.info("Verwende Konfiguration aus Docker Secrets")
            config.update(secrets_config)
        else:
            # Fall back to config.json
            config_file = os.getenv("CONFIG_FILE", "config.json")
            if os.path.exists(config_file):
                logging.info(f"Verwende Konfiguration aus {config_file}")
                with open(config_file, "r") as f:
                    config = json.load(f)
            else:
                logging.error("Keine Konfiguration gefunden! Bitte config.json, Umgebungsvariablen oder Docker Secrets bereitstellen.")
                sys.exit(1)

    valid_browsers = ["chromium", "firefox", "webkit"]
    browser = config.get("BROWSER", "chromium").lower()

    if browser not in valid_browsers:
        logging.warning(f"Ungültiger Browserwert '{browser}' in config - fallback auf 'chromium'")
        browser = "chromium"

    config["BROWSER"] = browser
    return config

def load_docker_secrets():
    """Lädt Konfiguration aus Docker Secrets"""
    secrets_dir = "/run/secrets"
    if not os.path.exists(secrets_dir):
        return None
    
    config = {}
    secret_files = {
        "RUFNUMMER": "at_extender_rufnummer",
        "PASSWORT": "at_extender_passwort",
        "TELEGRAM": "at_extender_telegram",
        "BOT_TOKEN": "at_extender_bot_token",
        "CHAT_ID": "at_extender_chat_id",
        "AUTO_UPDATE": "at_extender_auto_update",
        "SLEEP_MODE": "at_extender_sleep_mode",
        "SLEEP_INTERVAL": "at_extender_sleep_interval",
        "BROWSER": "at_extender_browser"
    }
    
    for key, secret_file in secret_files.items():
        secret_path = os.path.join(secrets_dir, secret_file)
        if os.path.exists(secret_path):
            try:
                with open(secret_path, "r") as f:
                    config[key] = f.read().strip()
            except Exception as e:
                logging.warning(f"Konnte Secret {secret_file} nicht lesen: {e}")
    
    # Check if we have the required secrets
    if config.get("RUFNUMMER") and config.get("PASSWORT"):
        return config
    
    return None


config = load_config()

RUFNUMMER = config["RUFNUMMER"]
PASSWORT = config["PASSWORT"]
BOT_TOKEN = config["BOT_TOKEN"]
CHAT_ID = config["CHAT_ID"]
AUTO_UPDATE = config["AUTO_UPDATE"]
TELEGRAM = config["TELEGRAM"]
SLEEP_MODE = config["SLEEP_MODE"]
SLEEP_INTERVAL = config["SLEEP_INTERVAL"]
BROWSER = config["BROWSER"]

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

LAST_GB = 0.0

# Set up data directory for Docker persistence
DATA_DIR = os.getenv("DATA_DIR", "/app/data" if os.path.exists("/app/data") else ".")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
COOKIE_FILE = os.path.join(DATA_DIR, "cookies.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

try:
    with open(STATE_FILE, "r") as f:
        data = json.load(f)
        if isinstance(data, dict) and "last_gb" in data:
            LAST_GB = float(data["last_gb"])
        else:
            raise ValueError("Ungültiges Format in state.json - setze zurück.")
except Exception as e:
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_gb": 0.0}, f)
    except Exception as save_error:
        logging.error(f"Konnte 'state.json' nicht neu erstellen: {save_error}")


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
        deny_selector = 'button[data-testid="uc-deny-all-button"]'
        try:
            button = page.query_selector(deny_selector)
            if button and button.is_visible():
                logging.info("Achtung Krümelmonster")
                button.click()
                time.sleep(1)
                if not button.is_visible():
                    logging.info("Cookie geschlossen (Banner verschwunden).")
                else:
                    logging.warning("Geklickt, aber Button scheint noch da zu sein.")
                return
        except Exception:
            logging.info("Keine Arme, keine Kekse.")

        deny_keywords = ["Verweigern", "Ablehnen", "Decline"]
        buttons = page.query_selector_all("button")

        for button in buttons:
            try:
                text = button.text_content().strip().lower()
                if any(keyword.lower() in text for keyword in deny_keywords):
                    if button.is_visible():
                        logging.info(f" Cookie Text gefunden: '{text}'")
                        try:
                            button.click()
                            time.sleep(1)
                            if not button.is_visible():
                                logging.info("Cookie geschlossen (Banner verschwunden).")
                            else:
                                logging.warning("Geklickt, aber Button scheint noch da zu sein.")
                        except Exception as click_error:
                            logging.warning(f"Cookie konnte nicht geschlossen werden: {click_error}")
                        return
            except Exception:
                continue

        logging.info("Nom Nom Nom")
    except Exception as e:
        logging.warning(f"Fehler im handle_cookie_banner:  {e}")

def goto_and_handle_cookies(page, url, wait_until="domcontentloaded", sleep_after=0):
    page.goto(url, wait_until=wait_until)
    if sleep_after:
        time.sleep(sleep_after)
    handle_cookie_banner(page)

def wait_and_handle_cookies(page, state="domcontentloaded", sleep_after=0):
    page.wait_for_load_state(state)
    if sleep_after:
        time.sleep(sleep_after)
    handle_cookie_banner(page)


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
                COOKIE_FILE = os.path.join(DATA_DIR, "cookies.json")
                logging.info(f"Starte {BROWSER}...")
                LAUNCH_ARGS = get_launch_args(BROWSER)

                proxy_settings = {"server": "http://127.0.0.1:8080"}

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
                goto_and_handle_cookies(page, DASHBOARD_URL, sleep_after=3)

                # Prüfen ob auf Login-Seite umgeleitet wurde
                if "login" in page.url:
                    logging.info("Nicht eingeloggt - Login wird durchgeführt...")
                    goto_and_handle_cookies(page, LOGIN_URL)

                    logging.info("Fülle Login-Daten aus...")
                    page.fill('#input-5', RUFNUMMER)
                    page.fill('#input-6', PASSWORT)

                    if not wait_and_click(page, '[class="button button--solid button--medium button--color-default button--has-label"]'):
                        raise Exception("Login-Button konnte nicht geklickt werden.")

                    logging.info("Warte auf Login...")
                    time.sleep(8)

                    if login_erfolgreich(page):
                        logging.info("Login erfolgreich - Cookies werden gespeichert.")
                        context.storage_state(path=COOKIE_FILE)
                    else:
                        raise Exception("Login fehlgeschlagen - Übersichtsseite nicht sichtbar.")
                else:
                    logging.info(" Bereits eingeloggt - Zugriff aufs Dashboard funktioniert.")

                    if not login_erfolgreich(page):
                        logging.warning("Session scheint abgelaufen oder fehlerhaft zu sein... versuche erneuten Login...")

                        if os.path.exists(COOKIE_FILE):
                            os.remove(COOKIE_FILE)
                            logging.info("Alte Cookies wurden gelöscht, da ungültig.")

                        browser.close()
                        logging.info("Browser wird für Neuanlauf geschlossen.")
                        time.sleep(3)
                        return login_and_check_data()

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
                    with open(STATE_FILE, "w") as f:
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
                            elements = page.query_selector_all(selector)
                            for button in elements:
                                if not button or not button.is_visible():
                                    continue
                                text = button.text_content().strip()
                                if "1 GB" in text or "1 GB" in text:
                                    if wait_and_click(page, selector):
                                        logging.info(f"Nachbuchungsbutton geklickt über Selector: {selector}")
                                        message = f"{RUFNUMMER}: Aktuelles Datenvolumen: {GB:.2f} GB – 1 GB wurde erfolgreich nachgebucht. 📲"
                                        send_telegram_message(message)
                                        clicked = True
                                        break
                            if clicked:
                                break
                        except Exception as e:
                            logging.warning(f"Fehler beim klicken: {e}")

                    if not clicked:
                        logging.info("Button nicht gefunden, Seite wird durchsuchst...")
                        try:
                            all_buttons = page.query_selector_all("one-button")
                            for btn in all_buttons:
                                try:
                                    if not btn or not btn.is_visible():
                                        continue
                                    text = btn.text_content().strip()
                                    logging.debug(f"Button-Text beim Durchlauf: {text}")
                                    if "1 GB" in text or "1 GB" in text:
                                        btn.click()
                                        logging.info("Fallback erfolgreich.")
                                        send_telegram_message(f"{RUFNUMMER}: Über Trick17 1 GB nachgebucht. 📲")
                                        clicked = True
                                        break
                                except Exception:
                                    continue
                        except Exception as fallback_error:
                            logging.warning(f"Fehler bei der Fallback Suche: {fallback_error}")

                    if not clicked:
                        raise Exception("Kein gültiger 1 GB Button gefunden – auch Fallback versagte.")

                else:
                    logging.info(f"Aktuelles Datenvolumen: {GB:.2f} GB")
                    send_telegram_message(f"{RUFNUMMER}: Noch {GB:.2f} GB übrig. Nächster Run in {interval} Sekunden. ✅")

                return get_interval(config)


            except Exception as e:
                logging.error(f"Fehler im Versuch {attempt+1}: {e}")
                send_telegram_message(f"{RUFNUMMER}: ❌ Fehler beim Abrufen des Datenvolumens: {e}")

            finally:
                if browser:
                    browser.close()
                    logging.info("Browser geschlossen.")

            time.sleep(2)
        logging.error("Skript hat nach 3 Versuchen aufgegeben.")
        return get_interval(config)

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
        time.sleep(interval if interval is not None else 90)
