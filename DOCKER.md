# Docker Bereitstellungsleitfaden für AT-Extender

Dieser Leitfaden bietet umfassende Anweisungen für die Bereitstellung von AT-Extender mit Docker.

## Schnellstart

### 1. Mit Docker Compose (Empfohlen)

```bash
# Repository klonen
git clone https://github.com/Dinobeiser/AT-Extender.git
cd AT-Extender

# Umgebungsdatei erstellen und bearbeiten
cp .env.example .env
# .env mit deinen Zugangsdaten bearbeiten

# Service starten
docker-compose up -d

# Logs prüfen
docker-compose logs -f
```

### 2. Mit Docker CLI

```bash
# Neuestes Image herunterladen
docker pull ghcr.io/dinobeiser/at-extender:latest

# Mit Umgebungsvariablen starten
docker run -d \
  --name at-extender \
  --restart unless-stopped \
  -e RUFNUMMER="deine_nummer" \
  -e PASSWORT="dein_passwort" \
  -e TELEGRAM="1" \
  -e BOT_TOKEN="dein_bot_token" \
  -e CHAT_ID="deine_chat_id" \
  -v at_extender_data:/app/data \
  ghcr.io/dinobeiser/at-extender:latest
```

## Konfigurationsmethoden

### Methode 1: Umgebungsvariablen

Konfiguration über Umgebungsvariablen in docker-compose.yml oder mit `-e` Flags:

```yaml
environment:
  - RUFNUMMER=deine_nummer
  - PASSWORT=dein_passwort
  - TELEGRAM=1
  - BOT_TOKEN=dein_bot_token
  - CHAT_ID=deine_chat_id
  - SLEEP_MODE=smart
  - BROWSER=chromium
```

### Methode 2: Konfigurationsdatei

Eine config.json Datei in den Container mounten:

```yaml
volumes:
  - ./config.json:/app/config.json:ro
  - at_extender_data:/app/data
```

### Methode 3: Docker Secrets (empfohlen)

```yaml
# docker-compose.secrets.yml
services:
  at-extender:
    image: ghcr.io/dinobeiser/at-extender:latest
    secrets:
      - at_extender_rufnummer
      - at_extender_passwort
      - at_extender_bot_token
      - at_extender_chat_id

secrets:
  at_extender_rufnummer:
    file: ./secrets/rufnummer.txt
  # ... weitere Secrets
```

## Volume-Verwaltung

### Datenpersistenz

Der Container speichert persistente Daten in `/app/data`:
- `state.json` - Aktueller Datenvolumen-Status
- `cookies.json` - Login-Session-Cookies

#### Named Volume (Empfohlen)
```yaml
volumes:
  - at_extender_data:/app/data
```

#### Host-Verzeichnis
```yaml
volumes:
  - ./data:/app/data
```

#### Berechtigungen setzen
```bash
# Für Host-Verzeichnisse
mkdir -p ./data
sudo chown 1000:1000 ./data

# Container-Benutzer-ID prüfen
docker run --rm ghcr.io/dinobeiser/at-extender:latest id
```

## Ressourcenverwaltung

### Speicher- und CPU-Limits

```yaml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '0.5'
    reservations:
      memory: 256M
      cpus: '0.1'
```

### Speicher-Optimierung

Für Server mit begrenztem RAM:

```yaml
environment:
  - BROWSER=firefox  # Manchmal speichereffizienter
```

## Monitoring und Health Checks

### Health Check Konfiguration

```yaml
healthcheck:
  test: ["CMD", "python", "healthcheck.py"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

### Container-Gesundheit prüfen

```bash
# Container-Status anzeigen
docker ps

# Detaillierte Gesundheitsinformationen
docker inspect at-extender | grep -A 10 Health

# Health Check Logs anzeigen
docker logs at-extender | grep health
```

### Log-Verwaltung

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

## Multi-Architektur-Unterstützung

### Verfügbare Architekturen

- `linux/amd64` - Intel/AMD 64-bit
- `linux/arm64` - ARM 64-bit (Raspberry Pi 4, Apple Silicon)

### Für spezifische Architektur erstellen

```bash
# Für ARM64 erstellen
docker buildx build --platform linux/arm64 -t at-extender:arm64 .

# Für beide Architekturen erstellen
docker buildx build --platform linux/amd64,linux/arm64 -t at-extender:multi .
```

## Image-Tags und Versionen

### Verfügbare Tags

- `ghcr.io/dinobeiser/at-extender:latest` - Neueste stabile Version
- `ghcr.io/dinobeiser/at-extender:v1.2.2` - Spezifische Version
- `ghcr.io/dinobeiser/at-extender:main` - Entwicklungsversionen

### Versionsfixierung

```yaml
# Auf spezifische Version festlegen
image: ghcr.io/dinobeiser/at-extender:v1.2.2

# Latest verwenden (Auto-Updates)
image: ghcr.io/dinobeiser/at-extender:latest
```

## Fehlerbehebung

### Häufige Probleme

#### Container stoppt sofort

```bash
# Logs auf Fehler prüfen
docker logs at-extender

# Häufige Ursachen:
# - Fehlende RUFNUMMER oder PASSWORT
# - Ungültige Zugangsdaten
# - Netzwerkverbindungsprobleme
```

#### Browser/Playwright-Probleme

```bash
# Anderen Browser versuchen
docker run -e BROWSER=firefox ...

# Prüfen ob Browser-Abhängigkeiten installiert sind
docker run --rm at-extender playwright install --dry-run
```

#### Berechtigungsfehler

```bash
# Volume-Berechtigungen korrigieren
sudo chown -R 1000:1000 ./data

# Mit anderem Benutzer ausführen (nicht empfohlen)
docker run --user root ...
```

#### Speicherprobleme

```bash
# Container-Speicherverbrauch überwachen
docker stats at-extender

# Speicherlimit erhöhen
# memory: 2G in docker-compose.yml setzen
```

### Debug-Modus

```bash
# Container interaktiv für Debugging ausführen
docker run -it --rm \
  -e RUFNUMMER="deine_nummer" \
  -e PASSWORT="dein_passwort" \
  ghcr.io/dinobeiser/at-extender:latest bash

# Python-Umgebung prüfen
python -c "import playwright; print('Playwright OK')"
```

### Log-Analyse

```bash
# Logs in Echtzeit verfolgen
docker logs -f at-extender

# Nach spezifischen Fehlern suchen
docker logs at-extender 2>&1 | grep -i fehler

# Logs zur Analyse exportieren
docker logs at-extender > at-extender.log 2>&1
```

## Sicherheitsüberlegungen

### Best Practices

1. **Docker Secrets verwenden** für sensible Daten
2. **Als Non-Root ausführen** (Standard: UID 1000)
3. **Container-Ressourcen begrenzen** um Ressourcenerschöpfung zu verhindern
4. **Spezifische Image-Tags verwenden** statt `latest` in der Produktion
5. **Container-Images regelmäßig aktualisieren**
6. **Logs auf Sicherheitsereignisse überwachen**

### Netzwerksicherheit

```yaml
# Netzwerkzugriff begrenzen falls nötig
networks:
  - internal

networks:
  internal:
    driver: bridge
    internal: true  # Kein Internetzugang
```

### Secrets-Verwaltung

```bash
# Externe Secrets-Verwaltung verwenden
# - Docker Swarm Secrets
# - Kubernetes Secrets
# - HashiCorp Vault
# - AWS Secrets Manager
```

## Produktionsbereitstellung

### Docker Swarm

```yaml
version: '3.8'
services:
  at-extender:
    image: ghcr.io/dinobeiser/at-extender:v1.2.2
    deploy:
      replicas: 1
      restart_policy:
        condition: on-failure
        delay: 10s
        max_attempts: 3
    secrets:
      - source: at_extender_config
        target: /run/secrets/at_extender_config
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: at-extender
spec:
  replicas: 1
  selector:
    matchLabels:
      app: at-extender
  template:
    metadata:
      labels:
        app: at-extender
    spec:
      containers:
      - name: at-extender
        image: ghcr.io/dinobeiser/at-extender:v1.2.2
        env:
        - name: RUFNUMMER
          valueFrom:
            secretKeyRef:
              name: at-extender-secrets
              key: rufnummer
        # ... weitere Umgebungsvariablen
```

## Backup und Wiederherstellung

### Daten-Backup

```bash
# Persistente Daten sichern
docker run --rm -v at_extender_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/at-extender-backup.tar.gz -C /data .
```

### Daten wiederherstellen

```bash
# Aus Backup wiederherstellen
docker run --rm -v at_extender_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/at-extender-backup.tar.gz -C /data
```

## Support

Für Docker-spezifische Probleme:
1. Diese Dokumentation prüfen
2. Container-Logs überprüfen: `docker logs at-extender`
3. Mit minimaler Konfiguration testen
4. Probleme auf GitHub mit Docker-Version und Konfiguration melden

Für allgemeine AT-Extender-Unterstützung:
- Telegram: @ATExtender_Usergroup
- GitHub Issues: https://github.com/Dinobeiser/AT-Extender/issues
