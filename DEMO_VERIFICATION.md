# EquiTie Demo — Manual Verification Guide

**Investor:** Idris Olawale (`INV001`)
**Reporting currency:** GBP
**Report date:** 2026-06-25
**FX rate:** 1 GBP = 1.35 USD (so divide any USD amount by 1.35 to get GBP)

**How to start:** open http://localhost:3000 → select **Idris Olawale (GBP)** → click **Enter portfolio**

---

## Question 1 — Portfolio MOIC

> **Ask:** "What is my overall portfolio MOIC?"

### Raw data

| Position | Units | Entry price | Latest price | Contributed (USD) |
|---|---|---|---|---|
| Forgecraft Robotics — Seed | 17,777.78 | $2.25 | $15.40 | $40,000 |
| Forgecraft Robotics — Series A | 4,487.18 | $7.80 | $15.366 | $35,000 |
| Forgecraft Robotics — Series B | 1,688.31 | $15.40 | $16.17 | $15,600 ¹ |
| Inferna AI — Series B | 7,405.41 | $18.50 | $29.97 | $137,000 |

¹ Series B committed = $26,000 but only 60% called so far; contributed = $15,600.

### Calculation

**Step 1 — Current value (units × latest price)**

| Position | Calculation | USD value |
|---|---|---|
| Forgecraft Seed | 17,777.78 × 15.40 | $273,777.81 |
| Forgecraft Series A | 4,487.18 × 15.366 | $68,950.01 |
| Forgecraft Series B | 1,688.31 × 16.17 | $27,299.97 |
| Inferna AI | 7,405.41 × 29.97 | $221,940.14 |
| **Total** | | **$591,967.93** |

**Step 2 — Convert total to GBP**

$591,967.93 ÷ 1.35 = **£438,494.76**

**Step 3 — Total contributed in GBP**

($40,000 + $35,000 + $15,600 + $137,000) ÷ 1.35
= $227,600 ÷ 1.35
= **£168,592.59**

**Step 4 — MOIC**

£438,494.76 ÷ £168,592.59 = **2.60×**

### Expected AI answer

- Portfolio MOIC ≈ **2.60×**
- Total current value ≈ **£438,495**
- Total contributed ≈ **£168,593**
- DPI = **0.0** (no distributions received yet)
- RVPI ≈ **2.60×** (all value is unrealised)

---

## Question 2 — Forgecraft multi-round breakdown

> **Ask:** "How is my Forgecraft Robotics investment performing across all three rounds?"

### Raw data

| Round | Entry price | Current price | Contributed | Units |
|---|---|---|---|---|
| Seed | $2.25 | $15.40 | $40,000 | 17,777.78 |
| Series A | $7.80 | $15.366 | $35,000 | 4,487.18 |
| Series B | $15.40 | $16.17 | $15,600 (60% of $26,000) | 1,688.31 |

### Calculation

**Step 1 — MOIC per round**

| Round | Formula | MOIC |
|---|---|---|
| Seed | $15.40 ÷ $2.25 | **6.84×** |
| Series A | $15.366 ÷ $7.80 | **1.97×** |
| Series B | $27,299.97 ÷ $15,600 ² | **1.75×** |

² Series B MOIC uses contributed ($15,600), not committed ($26,000).
Units were allocated on the full $26,000 commitment at $15.40 → 1,688.31 units.

**Step 2 — Current value per round in GBP**

| Round | USD value | ÷ 1.35 | GBP value |
|---|---|---|---|
| Seed | $273,777.81 | | **£202,798.38** |
| Series A | $68,950.01 | | **£51,074.08** |
| Series B | $27,299.97 | | **£20,222.20** |
| **Total** | **$370,027.79** | | **£274,094.66** |

**Step 3 — Total contributed (Forgecraft only)**

($40,000 + $35,000 + $15,600) ÷ 1.35
= $90,600 ÷ 1.35
= **£67,111.11**

### Expected AI answer

| Round | MOIC | Current value (GBP) | Notes |
|---|---|---|---|
| Seed | **6.84×** | **£202,798** | Biggest winner — entry at $2.25, now $15.40 |
| Series A | **1.97×** | **£51,074** | Nearly 2× |
| Series B | **1.75×** | **£20,222** | 60% contributed; $10,400 call still pending |
| **Total Forgecraft** | | **£274,095** | |

- Remaining Series B commitment = $10,400 → **£7,703.70** (due Sep 2026)

---

## Question 3 — Upcoming obligations

> **Ask:** "Do I have any overdue items, and what capital calls or fees are coming up?"

### Raw data

| Type | Deal | Amount (USD) | Due date | Status |
|---|---|---|---|---|
| Management Fee | Forgecraft Series B | $520 | 2026-05-01 | **OVERDUE** |
| Capital Call 2 | Forgecraft Series B | $10,400 | 2026-09-15 | Upcoming |
| Management Fee | Forgecraft Seed | $800 | 2026-07-15 | Upcoming |
| Admin Fee | Forgecraft Seed | $450 | 2026-07-15 | Upcoming |
| Management Fee | Forgecraft Series A | $700 | 2026-07-15 | Upcoming |
| Admin Fee | Forgecraft Series A | $450 | 2026-07-15 | Upcoming |
| Management Fee | Inferna AI | $1,370 | 2026-07-15 | Upcoming |

### Calculation

**Step 1 — Convert each to GBP (÷ 1.35)**

| Item | USD | GBP |
|---|---|---|
| Series B Management Fee (overdue) | $520 | **£385.19** |
| Series B Capital Call 2 | $10,400 | **£7,703.70** |
| Seed Management Fee | $800 | **£592.59** |
| Seed Admin Fee | $450 | **£333.33** |
| Series A Management Fee | $700 | **£518.52** |
| Series A Admin Fee | $450 | **£333.33** |
| Inferna AI Management Fee | $1,370 | **£1,014.81** |

**Step 2 — Totals**

Total fees (all 6): $4,290 ÷ 1.35 = **£3,177.77**
Capital call: $10,400 ÷ 1.35 = **£7,703.70**
Grand total: £3,177.77 + £7,703.70 = **£10,881.47**

> How management fees are calculated (for reference):
> Seed 2% × $40,000 = $800 | Series A 2% × $35,000 = $700 | Inferna AI 1% × $137,000 = $1,370
> Admin fees are always a flat $450/year regardless of deal currency.

### Expected AI answer

- **1 overdue fee:** Forgecraft Series B management fee = **£385.19**, was due 2026-05-01
- **1 upcoming capital call:** Forgecraft Series B Call 2 = **£7,703.70**, due 2026-09-15
- **5 upcoming fees** all due 2026-07-15 totalling ≈ **£2,792.58**
- **Grand total outstanding:** ≈ **£10,881.47**
