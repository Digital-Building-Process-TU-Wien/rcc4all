---
title: Vergleich
description: Vergleicht numerische Werte mit einem Zielwert oder Bereich und erzeugt harmonisierte Prüfelemente für die BCF-Ausgabe.
categories: validation
---

Der `comparison`-Node vergleicht numerische Werte (Ist-Werte) mit einem Zielwert
und erzeugt harmonisierte Prüfelemente, die mit dem `bcf_output`-Node kompatibel sind.
Er ist rein numerisch und IFC-agnostisch: Jede rohe Referenz (`inter:intersection_...`,
ein `<k1>_<k2>`-Abstands-Paar oder `<slug>:expr:<id>`) wird unverändert durchgereicht,
und der `bcf_output`-Node erweitert sie (über den gemeinsamen Helfer `expand_reference`)
zu IFC-Mitgliedsobjekten, damit BCF-Themen mit korrekten Ansichten erstellt werden können.

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
| `condition` | `Literal["equals","not_equals","lt","le","gt","ge","between","outside"]` | `"lt"` | Vergleichsoperator, der auf den Wert angewendet wird |
| `target_value` | `float` | `0.0` | Zielwert für Einzelwert-Operatoren (`equals`, `not_equals`, `lt`, `le`, `gt`, `ge`) |
| `target_min` | `float` | `0.0` | Untere Schranke für `between` / `outside`-Operatoren |
| `target_max` | `float` | `0.0` | Obere Schranke für `between` / `outside`-Operatoren |
| `inclusive_min` | `bool` | `True` | Wenn `True`, schließt der Bereich Werte ein, die gleich `target_min` sind (≥); sonst strikt größer (>) |
| `inclusive_max` | `bool` | `True` | Wenn `True`, schließt der Bereich Werte ein, die gleich `target_max` sind (≤); sonst strikt kleiner (<) |
| `abs_tol` | `float` | `0.001` | Absolute Toleranz zur Absorption von Gleitkomma-Rauschen nahe Grenzwerten. Angewendet auf `equals`/`not_equals`, `le`/`ge` und `between`/`outside` (nur inklusive Seiten); `lt`/`gt` bleiben strikt. Negative Werte werden als ihr absoluter Wert behandelt. |

## Eingaben

| Eingabe | Typ | Gebunden von | Beschreibung |
|---------|-----|--------------|--------------|
| `values` | `list[ComparisonValueItem]` | upstream node | Liste von Werten zum Vergleichen. Jeder Eintrag hat eine `reference` auf sein Quellelement und einen `value`. An ein Listen-Ausgangssignal eines upstream Nodes binden. |
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
- `passed_express_ids`, `failed_express_ids`: eine rohe Referenz pro
  bestandenem/gefeiltem Element (die Listenlänge entspricht also der Elementanzahl).
- `elements`: geordnete Liste von
  - `express_ids` (Liste mit der einzelnen, unveränderten rohen Referenz — z. B.
    `inter:intersection_...`, ein `<k1>_<k2>`-Paar oder `<slug>:expr:<id>`),
    `class_name` (`""`; wird pro Mitglied von `bcf_output` abgeleitet)
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

Für jedes `ComparisonValueItem` in `values`:

1. **Ein Element pro Eintrag emittieren (keine Auflösung, kein Dedup):** jedes
   `ComparisonValueItem` wird **ein Element**, das seine rohe `reference` unverändert
   trägt: `express_ids=[item.reference]`, `class_name=""`. Der Vergleich-Node löst
   nie Referenzen auf und überspringt nie — `bcf_output` erweitert die rohe Referenz
   zu Mitgliedsobjekten und verwirft, was es nicht erweitern kann.

2. **Bestanden/Nicht bestanden bestimmen:**
   - `missing = value is None or error is set or value is non-finite (NaN, +/-inf)` → `check.missing=True`, `failed=True`
   - Sonst numerischen Vergleich basierend auf `condition` unter Verwendung von `abs_tol` auswerten

Jedes Element trägt die einzelne `HarmonizedCheckResult`, die aus dem gebundenen
`check_parameter`/`unit` und den Zieleinstellungen aufgebaut wird.

**Zusammenfassungszahlen:** bestandene/gefeilte über alle Elemente aggregieren;
`passed_express_ids`/`failed_express_ids` enthalten eine rohe Referenz pro Element.

## Validierungen

- `check_parameter` nicht leer → `ValueError` (BCF `check.key` erforderlich).
- `target_min > target_max` für `between`/`outside` → `ValueError`.

## Hinweise

- **Konfigurierbare Toleranz:** `abs_tol` (Standard `0.001`) wird auf `equals`/`not_equals` (`math.isclose`), `le`/`ge` (Grenzwert-Erweiterung) und `between`/`outside` (nur inklusive Seiten) angewendet; `lt`/`gt` bleiben strikt. Negative Werte werden als ihr absoluter Wert behandelt.
- **Nicht-endliche Werte:** `NaN`, `+inf`, `-inf` werden als `missing=True, failed=True` klassifiziert, um in BCF sichtbar zu werden.
- **Referenz-/Klassen-Auflösung:** in den `bcf_output`-Node verlagert. Der Vergleich-Node reicht nur rohe Referenzen durch; `bcf_output` erweitert sie zu Mitgliedern und leitet die IFC-Klasse jedes Mitglieds über den gemeinsamen Helfer `expand_reference` in `openbim_runner.util.references` ab.
