#!/usr/bin/env python3
"""
Health Check Skript für AT-Extender Docker Container
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta

def check_health():
    """Prüft ob der AT-Extender Service gesund ist"""
    
    # Prüfen ob der Hauptprozess laufen sollte
    # Wir können die state.json prüfen um zu sehen ob sie kürzlich aktualisiert wurde
    data_dir = os.getenv("DATA_DIR", "/app/data")
    state_file = os.path.join(data_dir, "state.json")
    
    try:
        # Prüfen ob state.json existiert und kürzlich aktualisiert wurde
        if os.path.exists(state_file):
            stat_info = os.stat(state_file)
            last_modified = datetime.fromtimestamp(stat_info.st_mtime)
            
            # Als gesund betrachten wenn state.json in den letzten 2 Stunden aktualisiert wurde
            # (berücksichtigt smart sleep mode der lange Intervalle haben kann)
            if datetime.now() - last_modified < timedelta(hours=2):
                return True
            else:
                print(f"State-Datei zuletzt geändert: {last_modified}")
                return False
        else:
            # Falls noch keine state.json existiert, prüfen ob wir noch in der Startphase sind
            startup_time = timedelta(minutes=5)
            if hasattr(check_health, 'start_time'):
                if datetime.now() - check_health.start_time < startup_time:
                    return True
            else:
                check_health.start_time = datetime.now()
                return True
            
            return False
            
    except Exception as e:
        print(f"Health Check Fehler: {e}")
        return False

if __name__ == "__main__":
    if check_health():
        sys.exit(0)  # Gesund
    else:
        sys.exit(1)  # Ungesund
