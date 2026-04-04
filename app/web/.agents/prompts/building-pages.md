## Initial Prompt

Mockup the following Pages using the exisiting styling from main.css and taking inspiration from the index.vue (Use German language)

* Projects: A grid of projects with a placeholder image and their ttitle and subline (use a v-for to allow easy filling with real data)
* Single Project with file view split into documents and IFC and "Prüf-Ergebnisse", along side the versions of a project and an option to switch the published one and create a new version.
* User: A User page that allows chaning user email and password and name.
* Group Page: view groups, their memebrs, add users to a group, invite new users, change their rights (group admin), create new groups and sub groups

## Summary:
## Umfangreiche Zusammenfassung (für historische Dokumentation)

### Ziel der Aufgabe
Erstellung von vier neuen Nuxt-Seiten als **Mockups** in deutscher Sprache, **ausschließlich mit Tailwind CSS**, optisch konsistent zu den bestehenden Styles in `main.css` und dem Stil der bestehenden index.vue. Die Seiten sollten mit **v-for**-basierten Mock-Daten strukturiert sein, um später leicht echte Daten einzubinden. Zusätzlich sollten die neuen Seiten in der **Navigation** verlinkt werden.

### Umgesetzte Seiten (Routen)
1. **Projektübersicht**
   - Route: `/projects`
   - Inhalt: Grid aus Projekt-Karten mit Platzhalterbild, Titel und Subline.
   - Daten: Inline Mock-Array, Ausgabe via `v-for`.
   - Stil: Karten, Abstände, Typografie und Farben an das Muster aus index.vue angelehnt.

2. **Projekt-Detailseite**
   - Route: `/projects/[id]`
   - Inhalt:
     - **Versionen-Sektion** (inkl. veröffentlichter Version und „Neue Version“-Option)
     - **Dateibereich** mit getrennten Listen für **Dokumente** und **IFC**
     - **Prüf-Ergebnisse** als eigene visuelle Sektion
   - Struktur: sequenzieller Layout-Flow von oben nach unten, keine Tabs.
   - Daten: Inline Mock-Arrays mit `v-for`.

3. **User-Seite**
   - Route: `/account`
   - Inhalt: Formularbereiche zum Ändern von **Name**, **E-Mail** und **Passwort**.
   - Stil: Eingabefelder und Buttons im gleichen Karten-/Panel-Stil wie Startseite.

4. **Gruppen-Seite**
   - Route: `/groups`
   - Inhalt:
     - Listen von Gruppen und Mitgliedern
     - „User hinzufügen“, „User einladen“
     - Rollensteuerung (z. B. Gruppen-Admin)
     - Neue Gruppen/Subgruppen erstellen
   - Daten: Mock-Arrays per `v-for`.
   - Stil: Karten- und Abschnittsstruktur wie auf index.vue.

### Navigation
Die neuen Seiten wurden im **Header** der Standard-Layout-Datei verlinkt (Navigation bar), sodass alle neuen Routen direkt erreichbar sind.

### Design- und Stilprinzipien
- **Tailwind-only**, keine zusätzlichen CSS-Dateien.
- Typografie, Abstände, Karten-Styling, Farbverläufe und Buttons orientieren sich an index.vue.
- Sektionsstruktur mit Überschriften im Stil:
  - kleine Uppercase-Label
  - Hauptüberschrift
  - unterstützender Text
- Mock-Inhalte sind bewusst neutral gehalten, um später echte Daten einzusetzen.

### Ergebnis
Ein konsistenter, erweiterbarer Seiten-Satz im gleichen visuellen Stil wie die Startseite, mit klarer Struktur für spätere Datenanbindung und UI-Interaktionen.
