# Sporthalle Hamburg Event Crawler

Dieses Projekt bezieht Events von der [offiziellen Seite der Sporthalle Hamburg](https://termine.sporthallehamburg.de/pr/clipper.php) und veröffentlicht diese auf einem öffentlichen Kalender meiner [Nextcloud](https://nextcloud.com/) Instanz, von welcher er über eine WebDAV URL in einer vorhandenen Kalenderanwendung abonniert werden kann.

- Kalender: https://eule.wtf/SporthalleKalender
- WebDAV: https://eule.wtf/SporthalleKalenderSubscription

Die Startzeit eines Events richtet sich nach dem Einlass (Beginn falls nicht verfügbar) und das Ende richtet sich nach dem Beginn + 4 Stunden (Einlass + 6 Stunden falls nicht verfügbar). Bei Events ohne konkrete Zeitangaben der Sporthalle Hamburg wird die Zeit auf 16:00 - 22:00 Uhr gesetzt um diese, zumindest ungefähr, im Kalender abbilden zu können.

Neue Events oder Updates werden automatisch erkannt und im Kalender erstellt oder bearbeitet. Vergangene Events werden gelöscht sobald sie von der Seite der Sporthalle Hamburg gelöscht wurden.
