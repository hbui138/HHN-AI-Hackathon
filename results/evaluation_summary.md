# Evaluation summary

Source: pipeline_results_20260919_232139.json, pipeline_results_20260920_084638.json
All queries come from the held-out test split, never used for training or rule learning.

## All runs combined

- Queries: **2000**
- Top-1: **76.0%** · Top-3: **81.8%**
- Automation rate: **59.2%** (1185 lines)
- Auto-match precision: **95.4%** (54 wrong)
- Manual review: 815 lines, label in top-3 for 59.0%

### Per category (top-1 / top-3 / automation / auto precision)

| Category | n | Top-1 | Top-3 | Automation | Auto precision |
|---|---|---|---|---|---|
| bearings | 702 | 78.6% | 86.9% | 60.4% | 92.0% |
| pneumatics | 162 | 64.2% | 72.8% | 56.8% | 92.4% |
| standard_parts | 1136 | 76.1% | 79.8% | 58.9% | 98.1% |

### What the wrong auto-matches actually are (classified automatically from the codes)

| Type | Count | Share of wrong |
|---|---|---|
| Same product, variant the customer left open | 32 | 59.3% |
| Same product, but the customer did specify the detail | 8 | 14.8% |
| Different product | 14 | 25.9% |

**98.1%** of auto-matched lines are the labelled article or a variant of it that the customer left open. Same family does not always mean acceptable (a stainless variant nobody asked for is still wrong), so treat this as an upper bound.

### Trade-off: threshold and delta

| Threshold | Delta | Automation | Auto precision |
|---|---|---|---|
| 0.80 | 0.02 | 68.3% | 93.6% |
| 0.80 | 0.05 | 48.0% | 95.1% |
| 0.85 | 0.02 | 64.7% | 95.1% |
| 0.85 | 0.05 | 45.4% | 96.6% |
| 0.90 | 0.02 | 59.2% | 95.4% |
| 0.90 | 0.05 | 42.3% | 96.9% |
| 0.92 | 0.02 | 55.4% | 96.2% |
| 0.92 | 0.05 | 40.8% | 97.3% |
| 0.94 | 0.02 | 53.4% | 96.7% |
| 0.94 | 0.05 | 39.1% | 97.8% |
| 0.96 | 0.02 | 50.1% | 97.0% |
| 0.96 | 0.05 | 36.2% | 98.1% |

### Wrong auto-matches, one line each

| Query | Predicted | Label | Type |
|---|---|---|---|
| 252.24/1 | 111798 | 136128 | different_product |
| Flache Rändelschraube DIN 653-M5-20 / Hersteller: Ganter | 653-M5-20 | 653-M5-20-NI | variant_unspecified |
| 6308-Z C350 | 6308-Z | 6308-2Z/C3 | variant_unspecified |
| W?LZLAGER 6007 2Z | 6007-2Z | 6007-2Z/C3 | variant_unspecified |
| Alternative zum Kugelsperrbolzen K0642.14405060 baugleich! K | K0642.14405060 | K0366.24605060 | different_product |
| SKF 30302 (d=15mm;D=42mm;T=14,25) | 30302 | 30302 J2 | variant_unspecified |
| 236.J  | 111792 | 137524 | different_product |
| Einreihiges Kegelrollenlager  30205 | 30205 | 30205 J2/Q | variant_unspecified |
| RILLENKUGELLAGER / 61905 VV, RILLENKUGELLAGER, 61905 VV | 61905 | 61905-2RZ | variant_unspecified |
| Pilzknopf m. Gewindebolzen / M6x15, 06242-06_NORELEM | K0251.06 | K0251.06X15 | variant_specified |
| INA, FAG, SKF Koyo, EZO, GRW / 3305A / Schrägkugellager 25x6 | 3305 A | 3305 ATN9 | variant_unspecified |
| WAELZLAGER 6010 2Z | 6010-2Z | 6010-2Z/C3 | variant_unspecified |
| WAELZLAGER 6010 2Z | 6010-2Z | 6010-2Z/C3 | variant_unspecified |
| Rillenkugellager 61804-ZZ beidseitige Blechdichtung | W 61804-2Z | 61804-2RZ | variant_unspecified |
| Schrägkugellager 3208 A-2RS 1 DIN 628 | 3208 A-2RS1 | 3208 A-2RS1TN9/MT33 | variant_unspecified |
| Pendelkugellager 1313 EKTN9  | 1313 EKTN9 | 1313 EKTN9/C3 | variant_unspecified |
| Kugellager 627 ZTN9 | 627-ZTN9/LT | 627-Z | variant_specified |
| Spannhülse mit Ölbohrung nach Zeichnung - Gefertigt aus SPAN | H 3040 | OH 3040 H | variant_unspecified |
| MUFFE  252.24/2 * G1 INNEN L=40MM CUZN - 2.CUZN  7412.20.00  | 111799 | 136129 | different_product |
| Wie ID 10440679 aus AG 10196501 Kunde wünscht jedoch Edelsta | K0701.816 | K0701.916 | variant_unspecified |
| MUFFE  252.24/2 * G1 INNEN L=40MM CUZN - 2.CUZN  7412.20.00  | 111799 | 136129 | different_product |
| 6002-2Z | 6002-2Z | 6000-2Z | different_product |
| 1016346	 Kraftspanner	Ganter Norm	 864-32-BL | 864-32-BL | 864-32-BL-FG | variant_unspecified |
| Edelstahl Rillenkugellager SS 6006 2RS 30x55x13mm (deutsche  | 6006-2RS1/VT901 | W 6006-2RS1 | variant_unspecified |
| Rillenkugellager 6304  (Lagerspiel C3)  Artikelnummer 090000 | 6304-Z/C3 | 6304/C3 | variant_specified |
| 120626	Rillenkugellager d=15 D=32 B=9		SKF	6002-2Z | 6002-2Z | 16002-2Z | different_product |
| WINKEL-EINSCHRAUBVERSCHRAUBUNG / 112008 * N 90 * R 1/8 AG; R | 112008 | 109293 | different_product |
| RILLENKUGELLAGER 35/62X14 / 6007-2RS-INOX-NS7 | 6007-2RS1 | W 6007-2RS1 | variant_unspecified |
| Pilzknopf m. Gewindebolzen / M6x15, 06242-06_NORELEM | K0251.06 | K0251.06X15 | variant_specified |
| Klemmhebel M8x30 schwarz Grösse 3 KIPP K0122.3081X30 schwarz | K0122.3081X30 | K0122.3082X30 | variant_unspecified |
| BEARING SKF NR6205-2Z | 6205-2Z | 6205-2ZNR | variant_specified |
| ASK Kugellagerfabrik / 6304-2RS A2 / Rillenkugellager d=20 D | 6304-2RSH | W 6304-2RS1 | variant_unspecified |
| Wälzlager Rillenkugellager, einreihig Durchm. 32 x Durchm 12 | 6201 NR | 6201 | variant_specified |
| 1032643 / Rillenkugellager 6010 50X80X16 2RSR, Rillenkugella | 6010 | 6010-2RS1 | variant_unspecified |
| BS2-2212-2CS  | BS2-2212-2CSK/VT143 | BS2-2212-2RS/VT143 | variant_unspecified |
| Dünnringlager 61804VA  | 61804 | W 61804-2RS1 | different_product |
| 252.24/1 | 111798 | 136128 | different_product |
| Rillenkugellager, d015 D032 B09 VA  6002 2RS | 6002-2RSH/LT | W 6002-2RS1 | variant_unspecified |
| LA-Rillenkugel 61907-2RS1 SKF ------------------------------ | W 61907-2RS1 | 61907-2RS1 | variant_specified |
| Spannhülse mit Ölbohrung nach Zeichnung - Gefertigt aus SPAN | H 3040 | OH 3040 H | variant_unspecified |

## Run pipeline_results_20260919_232139 — seed 42, 1000 samples

- Queries: **1000**
- Top-1: **74.3%** · Top-3: **81.1%**
- Automation rate: **58.1%** (581 lines)
- Auto-match precision: **95.0%** (29 wrong)
- Manual review: 419 lines, label in top-3 for 58.5%

### Per category (top-1 / top-3 / automation / auto precision)

| Category | n | Top-1 | Top-3 | Automation | Auto precision |
|---|---|---|---|---|---|
| bearings | 342 | 76.3% | 86.0% | 58.8% | 91.0% |
| pneumatics | 89 | 61.8% | 71.9% | 53.9% | 89.6% |
| standard_parts | 569 | 75.0% | 79.6% | 58.3% | 98.2% |

### What the wrong auto-matches actually are (classified automatically from the codes)

| Type | Count | Share of wrong |
|---|---|---|
| Same product, variant the customer left open | 17 | 58.6% |
| Same product, but the customer did specify the detail | 4 | 13.8% |
| Different product | 8 | 27.6% |

**97.9%** of auto-matched lines are the labelled article or a variant of it that the customer left open. Same family does not always mean acceptable (a stainless variant nobody asked for is still wrong), so treat this as an upper bound.

### Trade-off: threshold and delta

| Threshold | Delta | Automation | Auto precision |
|---|---|---|---|
| 0.80 | 0.02 | 66.6% | 93.4% |
| 0.80 | 0.05 | 47.7% | 95.2% |
| 0.85 | 0.02 | 63.3% | 94.8% |
| 0.85 | 0.05 | 45.4% | 96.5% |
| 0.90 | 0.02 | 58.1% | 95.0% |
| 0.90 | 0.05 | 42.8% | 96.5% |
| 0.92 | 0.02 | 54.8% | 95.3% |
| 0.92 | 0.05 | 41.3% | 97.1% |
| 0.94 | 0.02 | 53.0% | 95.7% |
| 0.94 | 0.05 | 39.7% | 97.5% |
| 0.96 | 0.02 | 49.3% | 96.1% |
| 0.96 | 0.05 | 36.3% | 98.1% |

### Wrong auto-matches, one line each

| Query | Predicted | Label | Type |
|---|---|---|---|
| 252.24/1 | 111798 | 136128 | different_product |
| Flache Rändelschraube DIN 653-M5-20 / Hersteller: Ganter | 653-M5-20 | 653-M5-20-NI | variant_unspecified |
| 6308-Z C350 | 6308-Z | 6308-2Z/C3 | variant_unspecified |
| W?LZLAGER 6007 2Z | 6007-2Z | 6007-2Z/C3 | variant_unspecified |
| Alternative zum Kugelsperrbolzen K0642.14405060 baugleich! K | K0642.14405060 | K0366.24605060 | different_product |
| SKF 30302 (d=15mm;D=42mm;T=14,25) | 30302 | 30302 J2 | variant_unspecified |
| 236.J  | 111792 | 137524 | different_product |
| Einreihiges Kegelrollenlager  30205 | 30205 | 30205 J2/Q | variant_unspecified |
| RILLENKUGELLAGER / 61905 VV, RILLENKUGELLAGER, 61905 VV | 61905 | 61905-2RZ | variant_unspecified |
| Pilzknopf m. Gewindebolzen / M6x15, 06242-06_NORELEM | K0251.06 | K0251.06X15 | variant_specified |
| INA, FAG, SKF Koyo, EZO, GRW / 3305A / Schrägkugellager 25x6 | 3305 A | 3305 ATN9 | variant_unspecified |
| WAELZLAGER 6010 2Z | 6010-2Z | 6010-2Z/C3 | variant_unspecified |
| WAELZLAGER 6010 2Z | 6010-2Z | 6010-2Z/C3 | variant_unspecified |
| Rillenkugellager 61804-ZZ beidseitige Blechdichtung | W 61804-2Z | 61804-2RZ | variant_unspecified |
| Schrägkugellager 3208 A-2RS 1 DIN 628 | 3208 A-2RS1 | 3208 A-2RS1TN9/MT33 | variant_unspecified |
| Pendelkugellager 1313 EKTN9  | 1313 EKTN9 | 1313 EKTN9/C3 | variant_unspecified |
| Kugellager 627 ZTN9 | 627-ZTN9/LT | 627-Z | variant_specified |
| Spannhülse mit Ölbohrung nach Zeichnung - Gefertigt aus SPAN | H 3040 | OH 3040 H | variant_unspecified |
| MUFFE  252.24/2 * G1 INNEN L=40MM CUZN - 2.CUZN  7412.20.00  | 111799 | 136129 | different_product |
| Wie ID 10440679 aus AG 10196501 Kunde wünscht jedoch Edelsta | K0701.816 | K0701.916 | variant_unspecified |
| MUFFE  252.24/2 * G1 INNEN L=40MM CUZN - 2.CUZN  7412.20.00  | 111799 | 136129 | different_product |
| 6002-2Z | 6002-2Z | 6000-2Z | different_product |
| 1016346	 Kraftspanner	Ganter Norm	 864-32-BL | 864-32-BL | 864-32-BL-FG | variant_unspecified |
| Edelstahl Rillenkugellager SS 6006 2RS 30x55x13mm (deutsche  | 6006-2RS1/VT901 | W 6006-2RS1 | variant_unspecified |
| Rillenkugellager 6304  (Lagerspiel C3)  Artikelnummer 090000 | 6304-Z/C3 | 6304/C3 | variant_specified |
| 120626	Rillenkugellager d=15 D=32 B=9		SKF	6002-2Z | 6002-2Z | 16002-2Z | different_product |
| WINKEL-EINSCHRAUBVERSCHRAUBUNG / 112008 * N 90 * R 1/8 AG; R | 112008 | 109293 | different_product |
| RILLENKUGELLAGER 35/62X14 / 6007-2RS-INOX-NS7 | 6007-2RS1 | W 6007-2RS1 | variant_unspecified |
| Pilzknopf m. Gewindebolzen / M6x15, 06242-06_NORELEM | K0251.06 | K0251.06X15 | variant_specified |

## Run pipeline_results_20260920_084638 — seed 2026, 1000 samples

- Queries: **1000**
- Top-1: **77.7%** · Top-3: **82.4%**
- Automation rate: **60.4%** (604 lines)
- Auto-match precision: **95.9%** (25 wrong)
- Manual review: 396 lines, label in top-3 for 59.6%

### Per category (top-1 / top-3 / automation / auto precision)

| Category | n | Top-1 | Top-3 | Automation | Auto precision |
|---|---|---|---|---|---|
| bearings | 360 | 80.8% | 87.8% | 61.9% | 92.8% |
| pneumatics | 73 | 67.1% | 74.0% | 60.3% | 95.5% |
| standard_parts | 567 | 77.1% | 80.1% | 59.4% | 97.9% |

### What the wrong auto-matches actually are (classified automatically from the codes)

| Type | Count | Share of wrong |
|---|---|---|
| Same product, variant the customer left open | 15 | 60.0% |
| Same product, but the customer did specify the detail | 4 | 16.0% |
| Different product | 6 | 24.0% |

**98.3%** of auto-matched lines are the labelled article or a variant of it that the customer left open. Same family does not always mean acceptable (a stainless variant nobody asked for is still wrong), so treat this as an upper bound.

### Trade-off: threshold and delta

| Threshold | Delta | Automation | Auto precision |
|---|---|---|---|
| 0.80 | 0.02 | 70.1% | 93.7% |
| 0.80 | 0.05 | 48.4% | 95.0% |
| 0.85 | 0.02 | 66.1% | 95.3% |
| 0.85 | 0.05 | 45.4% | 96.7% |
| 0.90 | 0.02 | 60.4% | 95.9% |
| 0.90 | 0.05 | 41.8% | 97.4% |
| 0.92 | 0.02 | 56.0% | 97.1% |
| 0.92 | 0.05 | 40.4% | 97.5% |
| 0.94 | 0.02 | 53.9% | 97.8% |
| 0.94 | 0.05 | 38.6% | 98.2% |
| 0.96 | 0.02 | 51.0% | 97.8% |
| 0.96 | 0.05 | 36.2% | 98.1% |

### Wrong auto-matches, one line each

| Query | Predicted | Label | Type |
|---|---|---|---|
| Klemmhebel M8x30 schwarz Grösse 3 KIPP K0122.3081X30 schwarz | K0122.3081X30 | K0122.3082X30 | variant_unspecified |
| BEARING SKF NR6205-2Z | 6205-2Z | 6205-2ZNR | variant_specified |
| ASK Kugellagerfabrik / 6304-2RS A2 / Rillenkugellager d=20 D | 6304-2RSH | W 6304-2RS1 | variant_unspecified |
| Wälzlager Rillenkugellager, einreihig Durchm. 32 x Durchm 12 | 6201 NR | 6201 | variant_specified |
| 1032643 / Rillenkugellager 6010 50X80X16 2RSR, Rillenkugella | 6010 | 6010-2RS1 | variant_unspecified |
| BS2-2212-2CS  | BS2-2212-2CSK/VT143 | BS2-2212-2RS/VT143 | variant_unspecified |
| Dünnringlager 61804VA  | 61804 | W 61804-2RS1 | different_product |
| 252.24/1 | 111798 | 136128 | different_product |
| Rillenkugellager, d015 D032 B09 VA  6002 2RS | 6002-2RSH/LT | W 6002-2RS1 | variant_unspecified |
| LA-Rillenkugel 61907-2RS1 SKF ------------------------------ | W 61907-2RS1 | 61907-2RS1 | variant_specified |
| Spannhülse mit Ölbohrung nach Zeichnung - Gefertigt aus SPAN | H 3040 | OH 3040 H | variant_unspecified |
| Lager6005-2RSR | 2026005-2RSR | 6005-2RSH | different_product |
| Radial-Kugellager RILLENKUGELLAGER-6006-2RS-SKF Bitte ggf. M | W 6006-2RS1 | 6006-2RS1 | variant_unspecified |
| Griffstange d10x80 Nirosta Form A GN310-10-80-A-NI GANTER | 310-10-80-A-NI | 310-10-80-A-ZB | variant_unspecified |
| DIN 6319-D 9,6-St - Kegelpfanne 23050.0108 /Halder 07420-208 | K0729.208 | 6319-9,6-D | different_product |
| SKF 30302 (d=15mm;D=42mm;T=14,25) | 30302 | 30302 J2 | variant_unspecified |
| 10663460  | 106634 | 110529 | different_product |
| Pilzknopf m. Gewindebolzen / M6x15, 06242-06_NORELEM | K0251.06 | K0251.06X15 | variant_specified |
| Alternative zum Kugelsperrbolzen K0642.14405060 baugleich! K | K0642.14405060 | K0366.24605060 | different_product |
| Rillenkugellager (ITG Art.-Nr.: p0022500) (6006-Z) | 6006-Z | 6006-2Z | variant_unspecified |
| Kugellager 3212 A-2RS1  | 3212 A-2RS1 | 3212 A-2RS1TN9/MT33 | variant_unspecified |
| SS 6001 ZZ Edelstahllager  | 6001-2Z | W 6001-2Z | variant_unspecified |
| Wie ID 10440679 aus AG 10196501 Kunde wünscht jedoch Edelsta | K0701.816 | K0701.916 | variant_unspecified |
| W?LZLAGER 6007 2Z | 6007-2Z | 6007-2Z/C3 | variant_unspecified |
| Raendelschraube hoch DIN464 / M8x16 d30 DIN464 M8x16 d30 060 | K0140.08X16 | K0140.082X16 | variant_unspecified |
