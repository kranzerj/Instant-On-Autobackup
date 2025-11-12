# Instant ON Autobackup

Automatisches Backup-Tool für Aruba Instant On Switch Konfigurationen mit Generationenprinzip-Archiv.

## Lizenz
GPL-3.0 License

## Credits
- Basierend auf: [aruba-1830-cert-uploader](https://github.com/travatine/aruba-1830-cert-uploader) von travatine
- Erstellt von: Claude (Anthropic)
- Im Auftrag von: Josef Kranzer (COUNT IT)

## Beschreibung
Dieses Script liest eine `config.json` aus und erstellt automatisch Backups der Running Config von allen konfigurierten Aruba Instant On Switches.

### Features
- **Automatisches Backup** der Running Configuration
- **Hostname-Erkennung** aus der Switch-Konfiguration
- **Generationenprinzip-Archiv** mit 7 Tages-, 4 Wochen-, 12 Monats- und 3 Jahres-Backups
- **Individuelle Archiv-Steuerung** pro Switch

### Backup-Dateien
- Aktuelles Backup: `{hostname}.running.config.txt` im Script-Verzeichnis
- Archiv: `Archiv-{hostname}/` mit datierten Backups

## Voraussetzungen

**Benötigte Python-Module:**
```bash
pip install requests pycryptodome
```

Oder mit requirements.txt:
```bash
pip install -r requirements.txt
```

## Konfiguration
Erstelle eine `config.json` im gleichen Verzeichnis wie das Script:

```json
{
  "switches": [
    {
      "hostname_IP": "10.28.150.55",
      "user": "backup-user",
      "password": "secure-password",
      "archive": true
    },
    {
      "hostname_IP": "switch02.example.org",
      "user": "admin",
      "password": "password",
      "archive": false
    }
  ]
}
```

### Parameter
- `hostname_IP`: IP-Adresse oder Hostname des Switches
- `user`: Benutzername (benötigt Schreibrechte sonst ist kein Backup möglich)
- `password`: Passwort des Benutzers
- `archive`: `true` = Archiv aktiviert, `false` = nur aktuelles Backup (optional, Standard: false)

## Verwendung
```bash
python instant-on-autobackup.py
```

## Archiv-System (Generationenprinzip)

Wenn `"archive": true` gesetzt ist, wird ein strukturiertes Archiv angelegt:

### Struktur
```
Script-Verzeichnis/
├── nlnzswiIOStack1.running.config.txt          # Aktuelles Backup
├── Archiv-nlnzswiIOStack1/
│   ├── nlnzswiIOStack1-2025-11-12-daily.running.config.txt
│   ├── nlnzswiIOStack1-2025-11-11-daily.running.config.txt
│   ├── nlnzswiIOStack1-2025-11-04-weekly.running.config.txt
│   ├── nlnzswiIOStack1-2025-10-31-monthly.running.config.txt
│   └── nlnzswiIOStack1-2024-12-31-yearly.running.config.txt
```

### Generationen
- **Daily (7 Stück)**: Tägliche Backups der letzten 7 Tage
- **Weekly (4 Stück)**: Ältestes Daily wird zu Weekly
- **Monthly (12 Stück)**: Ältestes Weekly wird zu Monthly
- **Yearly (3 Stück)**: Letztes Backup des alten Jahres wird zu Yearly

### Mehrfach-Backups am Tag
Wenn das Script mehrmals täglich läuft, werden Backups mit Uhrzeit versehen:
- `nlnzswiIOStack1-2025-11-12-14-30-daily.running.config.txt`

### Datumsbasis
Die Archivierung basiert auf dem **Änderungsdatum der Backup-Datei**, nicht auf der Script Laufzeit.

## Empfehlungen
- Erstelle einen dedizierten User mit Schreibrechte auf den Switches für Backups 
- Führe das Script regelmäßig via Cronjob/Task Scheduler aus (z.B. täglich)
- Sichere die config.json, da sie Passwörter enthält
- Aktiviere Archiv für produktive Switches (`"archive": true`)

## Beispiel Windows Task Scheduler
1. Task Scheduler öffnen
2. "Einfache Aufgabe erstellen"
3. Trigger: Täglich um 2:00 Uhr
4. Aktion: `python C:\Pfad\zu\instant-on-autobackup.py`
5. Startverzeichnis: `C:\Pfad\zu\`

## Getestet mit
- Aruba Instant On 1960 Stack - Firmware 3.3.0 - local Mangament

## Technische Details
- Verwendet HTTP für Kommunikation (Credentials werden RSA-verschlüsselt übertragen)
- Self-signed Zertifikate sind kein Problem
- Session-Cookies werden automatisch verwaltet

## Hinweis
Die Aruba Instant On Switches haben keine offizielle API. Dieses Tool basiert auf der Analyse der HTTP-Requests der Web-GUI.

**Startup Config Backup wird nicht unterstützt**, da der Switch bei diesem Request die Verbindung abbricht (vermutlich ein Bug in der Switch-Firmware).
