# AT-Extender

## 🛠️ Setup-Anleitung

AT-Extender ist ein Python-Skript, das automatisch das verbleibende Datenvolumen eines Aldi Talk Tarifs überprüft und bei Bedarf über das Kundenportal nachbucht. Die Benachrichtigung erfolgt über Telegram.

---

## ✅ Voraussetzungen

### 1. Allgemeine Anforderungen
- **Python 3.8 oder höher** muss installiert sein.
- **Playwright** muss installiert sein.
- Eine **Aldi Talk Rufnummer & Passwort**.
- Ein **Telegram-Bot Token & Chat-ID** für Benachrichtigungen.

### 2. Betriebssystemspezifische Abhängigkeiten

#### **Linux/macOS**
```bash
# Systemabhängigkeiten installieren (Debian/Ubuntu)
sudo apt update && sudo apt install -y python3 python3-pip unzip

# Optional für macOS
brew install python3 unzip
```

#### **Windows**
1. **[Python 3.8+](https://www.python.org/downloads/)** installieren.
2. Während der Installation **"Add Python to PATH"** aktivieren.
3. Playwright erfordert zusätzliche Bibliotheken, die automatisch installiert werden.

---

## 🎯 Installation

### **1. Repository klonen**
```bash
git clone https://github.com/Dinobeiser/AT-Extender.git
cd AT-Extender
```

### **2. Virtuelle Umgebung erstellen und aktivieren**

#### **Linux/macOS**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### **Windows (CMD/Powershell)**
```powershell
python -m venv venv
venv\Scripts\activate
```

### **3. Abhängigkeiten installieren**
```bash
pip install playwright requests
playwright install
```

---

## ⚙️ Konfiguration

Öffne das Skript `aldi.py` und editiere die folgenden Variablen mit deinen Zugangsdaten:

```python
RUFNUMMER = "DeineRufnummer"
PASSWORT = "DeinPasswort"
BOT_TOKEN = "DeinTelegramBotToken"
CHAT_ID = "DeineChatID"
```

---

## ⚡ Nutzung

### **Manuell starten**
```bash
python aldi.py
```

### **Automatischer Start bei Systemneustart**

#### **Linux/macOS (via systemd)**
1. **Service-Datei erstellen:**
```bash
nano /etc/systemd/system/aldi.service
```

2. **Folgendes einfügen:**
```ini
[Unit]
Description=Aldi Talk Datenautomatisierung
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/aldi/AT-Extender
ExecStart=/home/ubuntu/venv/bin/python /home/aldi/AT-Extender/aldi.py
Restart=no

[Install]
WantedBy=multi-user.target
```

3. **Service aktivieren & starten:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable aldi.service
sudo systemctl start aldi.service
```

4. **Status überprüfen:**
```bash
sudo systemctl status aldi.service
```

#### **Windows (via Task Scheduler)**
1. **Task Scheduler öffnen** (`taskschd.msc` im Startmenü eingeben).
2. **Neuen Task erstellen** → Name vergeben (`AT-Extender`).
3. **Trigger:** "Bei Systemstart" auswählen.
4. **Aktion:** "Programm starten" → `C:\Pfad\zu\python.exe C:\Pfad\zu\aldi.py`
5. **OK klicken und testen.**

---

## 🛡️ Überwachung & Neustart bei Abstürzen

### **Linux/macOS (Watchdog mit `cron` und `screen`)**
1. **Script für Neustart erstellen:**
```bash
echo '#!/bin/bash
if ! pgrep -f "aldi.py" > /dev/null; then
    screen -dmS aldi /home/ubuntu/venv/bin/python /home/aldi/AT-Extender/aldi.py
fi' > /home/aldi/watchdog.sh
chmod +x /home/aldi/watchdog.sh
```

2. **In `crontab` eintragen:**
```bash
crontab -e
```
Füge am Ende hinzu:
```bash
* * * * * /home/aldi/watchdog.sh
```

Damit wird das Skript **jede Minute überprüft** und falls es nicht läuft, neu gestartet.

### **Windows (via Task Scheduler & Batch-Skript)**
1. **Batch-Skript erstellen (`watchdog.bat`)**
```batch
@echo off
tasklist | findstr /I "python.exe" >nul || start "" python.exe C:\Pfad\zu\aldi.py"
```
2. **Task erstellen (wie oben, aber alle 5 Min starten).**

---

## ⏰ Automatischer Neustart des Servers um 3 Uhr nachts

#### **Linux/macOS**
```bash
sudo crontab -e
```
Füge hinzu:
```bash
0 3 * * * /sbin/shutdown -r now
```

#### **Windows**
```powershell
schtasks /create /tn "Reboot" /tr "shutdown /r /f /t 0" /sc daily /st 03:00
```

---

## 🐝 Feedback & Verbesserungen
Falls du Verbesserungsvorschläge hast oder Fehler findest, öffne ein Issue auf GitHub oder erstelle einen Pull Request! 🎉

