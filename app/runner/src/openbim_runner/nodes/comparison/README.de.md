---
title: Vergleich
description: Vergleicht gemessene numerische Werte mit einem Zielwert oder Bereich und erzeugt harmonisierte Prüfelemente für die BCF-Ausgabe.
categories: validation
---

Der `comparison`-Node vergleicht berechnete Messwerte (Ist-Werte) mit einem Zielwert
und erzeugt harmonisierte Prüfelemente, die mit dem `bcf_output`-Node kompatibel sind.
Der Vergleich-Node löst Hilfsgeometrie-Referenzen (`inter:intersection_...`,
Abstands-Paar-Referenzen) zurück zu IFC-Elementreferenzen auf, damit BCF-Themen
mit korrekten Ansichten erstellt werden können.

## Anwendungsbeispiel

```
collision → measurement → comparison → bcf_output
```

1. **Collision-Node** erkennt sich schneidende Elemente und erzeugt `intersection_meshes`
2. **Measurement-Node** berechnet das Volumen jedes Schnittmengennetzes
3. **Comparison-Node** vergleicht jedes Volumen mit einem Zielwert (z. B. `0.0` für jede Kollision) und emittiert harmonisierte Elemente
4. **BCF-Output** erstellt BCF 3.0-Themen mit Ansichten für jedes kollidierende Element

## Einstellungen

| Einstellung | Typ | Standard | Beschreibung |
|-------------|-----|----------|--------------|
| `condition` | `Literal["equals","not_equals","lt","le","gt","ge","between","outside"]` | `"lt"` | Vergleichsoperator, der auf den Messwert angewendet wird |
| `target_value` | `float` | `0.0` | Zielwert für Einzelwert-Operatoren (`equals`, `not_equals`, `lt`, `le`, `gt`, `ge`) |
| `target_min` | `float` | `0.0` | Untere Schranke für `between` / `outside`-Operatoren |
| `target_max` | `float` | `0.0` | Obere Schranke für `between` / `outside`-Operatoren |
| `inclusive_min` | `bool` | `True` | Wenn `True`, schließt der Bereich Werte ein, die gleich `target_min` sind (≥); sonst strikt größer (>) |
| `inclusive_max` | `bool` | `True` | Wenn `True`, schließt der Bereich Werte ein, die gleich `target_max` sind (≤); sonst strikt kleiner (<) |
| `abs_tol` | `float` | `0.001` | Absolute Toleranz zur Absorption von Gleitkomma-Rauschen nahe Grenzwerten. Angewendet auf `equals`/`not_equals`, `le`/`ge` und `between`/`outside` (nur inklusive Seiten); `lt`/`gt` bleiben strikt. Negative Werte werden als ihr absoluter Wert behandelt. |

## Eingaben

| Eingabe | Typ | Gebunden von | Beschreibung |
|---------|-----|--------------|--------------|
| `values` | `list[MeasurementItem]` | upstream node | Liste von Werten zum Vergleichen. An ein Listen-Ausgangssignal eines upstream Nodes binden. |
| `unit` | `str` | upstream node | Maßeinheit der verglichenen Werte. An ein Einheiten-Ausgangssignal eines upstream Nodes binden, z. B. `measurement.unit`. |
| `check_parameter` | `str` | upstream node | Bezeichnung für die Prüfung (wird zum BCF-Prüfschlüssel). An ein Typ-/Prüfparameter-Ausgangssignal eines upstream Nodes binden, z. B. `measurement.type`. |

## Ausgaben

Das Ergebnis ist eine schlanke, strukturierte Prüfung pro Element. Der Executor
kapselt jedes Knotenergebnis in einen Umschlag `{ label, type, result }`, wobei
`label` (zur Laufzeit zugewiesener Name) und `type` (`"comparison"`) auf dem
äußeren Umschlag liegen — das `result`-Objekt des Nodes selbst enthält nur die
folgenden Felder:

- `summary_element_count` (verarbeitete Elemente), `summary_passed_count` /
  `summary_failed_count` (auf Elementebene: Elemente mit bestandener/gefeilter
  Prüfung) und `summary_check_count` (Gesamtzahl der Prüfungen, entspricht der
  Elementanzahl).
- `passed_express_ids`, `failed_express_ids`: flache Listen qualifizierter
  Referenzen, die die geprüften Elemente partitionieren.
- `elements`: geordnete Liste von
  - `express_ids` (Liste, normalerweise eine einzelne qualifizierte Referenz),
    `class_name` (IFC-Klasse oder `unknown`), `intersection` (ursprüngliche
    `inter:intersection_...`-Referenz für Kollisionsschnittmengen; `""` sonst)
  - `failed`: wahr, wenn die Prüfung fehlgeschlagen ist
  - `checks`: Liste von `HarmonizedCheckResult` (eine pro Element):
    - `key`: der gebundene `check_parameter` (z. B. `volume`)
    - `check_parameter`: die gebundene Eingabe
    - `expected_value`: `str(target_value)` (Einzelwert-Operatoren) oder `""` (Bereich)
    - `actual_value`: `str(value)` oder `""` (fehlend)
    - `unit`: gebundene Eingabe
    - `missing`: `True`, wenn Wert `None` ist, einen Fehler hat oder nicht endlich (`NaN`, `+/-inf`)
    - `passed`: nicht fehlend und Vergleich besteht
    - `expected_value_condition`: `condition`
    - `expected_value_min`: `str(target_min)` (between/outside) oder `""`
    - `expected_value_max`: `str(target_max)` (between/outside) oder `""`

## Verhalten

Für jedes `MeasurementItem` in `values`:

1. **Referenz auflösen → IFC-Element(e):**
   - `<slug>:expr:<id>` → einzelnes Element mit `express_ids=[ref]`
   - `inter:intersection_<k1>_<k2>` (Kollisionsschnittmenge) → beide zugrundeliegenden Schlüssel parsen; wenn beide `:expr:`-Referenzen sind, **ein Element** mit `express_ids=[refA, refB]` (beide Mitglieder) emittieren; sonst überspringen
   - `<expr1>_<expr2>` (Abstands-Paar-Referenz, z. B. `main:expr:17_main:expr:45`) → beide Schlüssel parsen; wenn beide `:expr:`-Referenzen sind, **ein Element** mit `express_ids=[refA, refB]` emittieren; sonst überspringen
   - `gen:...`, `inter:` (nicht-Schnittmenge) oder ungültig → überspringen (kein Element emittiert)

2. **Bestanden/Nicht bestanden bestimmen:**
   - `missing = value is None or error is set or value is non-finite (NaN, +/-inf)` → `check.missing=True`, `failed=True`
   - Sonst numerischen Vergleich basierend auf `condition` unter Verwendung von `abs_tol` auswerten

3. **`HarmonizedElement` pro `MeasurementItem` emittieren** (kein Dedup) mit der einzelnen Prüfung.

4. **Zusammenfassungszahlen:** bestandene/gefeilte aus allen Elementen aggregieren.

## Validierungen

- `check_parameter` nicht leer → `ValueError` (BCF `check.key` erforderlich).
- `target_min > target_max` für `between`/`outside` → `ValueError`.

## Hinweise

- **Konfigurierbare Toleranz:** `abs_tol` (Standard `0.001`) wird auf `equals`/`not_equals` (`math.isclose`), `le`/`ge` (Grenzwert-Erweiterung) und `between`/`outside` (nur inklusive Seiten) angewendet; `lt`/`gt` bleiben strikt. Negative Werte werden als ihr absoluter Wert behandelt.
- **Nicht-endliche Werte:** `NaN`, `+inf`, `-inf` werden als `missing=True, failed=True` klassifiziert, um in BCF sichtbar zu werden.
- **class_name-Auflösung:** wird aus dem IFC-Modell nach Slug aufgelöst; fällt auf `"unknown"` zurück, wenn das Element nicht gefunden wird.
