# Myanmar Pre-Coup Calibration Reference

*Collected for the Myanmar development simulation ("no-coup" counterfactual). This document pairs the **democratic government's forward plans** (the targets a no-coup scenario should aim at) with the **empirical pre-coup trajectory** (the pre-2021 series to calibrate against). Qualitative policy targets come from official plans; hard numeric series should be pulled live from the World Bank / IMF (see §4).*

---

## 1. The empirical pre-coup trajectory (2011–2020)

The reform era began in 2011 under President Thein Sein's transitional government and continued under the NLD government elected in 2015. Over 2011–2019 the economy grew ~6%/yr on average with major poverty reduction, driven by economic liberalization and the lifting of Western sanctions.

**Real GDP growth (%), calendar-year basis (IMF/Wikipedia)** — use as the synthetic-control pre-treatment outcome series:

| Year | Real GDP growth |
|------|-----------------|
| 2011 | 5.5% |
| 2012 | 6.5% |
| 2013 | 7.9% |
| 2014 | 8.2% |
| 2015 | 7.5% |
| 2016 | 6.4% |
| 2017 | 5.8% |
| 2018 | 6.4% |
| 2019 | 6.8% |
| 2020 | −1.2% (COVID shock, *not* the coup) |
| 2021 | data gap / coup year |
| 2022 | −4.0% |
| 2023 | 2.5% |
| 2024 | 1.0% |

**Other structural facts (reform era):**
- **Poverty:** official headcount ~24.8% in 2017; rose to ~31% by 2023–24 post-coup (World Bank). Reform era roughly halved poverty from its earlier levels.
- **FDI:** rose sharply after 2011 as investment laws were rewritten and sanctions lifted; oil & gas and telecom were early magnets.
- **Telecom / connectivity (the key "innovation" story):** the 2013 telecom liberalization (licenses to Telenor and Ooredoo) broke the state monopoly. Mobile penetration and internet use went from near-zero to majority within ~5 years — a genuine leapfrog, plus mobile-money adoption (e.g. Wave Money) ahead of bank-account penetration.
- **Government debt:** fell from ~50% of GDP (2011) toward ~39–41% (2018–2020), then rose post-coup.

> ⚠️ **Calibration caveats:**
> 1. **2020 ≠ coup.** The −1.2% in 2020 is COVID; don't attribute it to the coup.
> 2. **Fiscal vs calendar year.** The World Bank reported an ~18% contraction for **FY2021** (Oct 2020–Sep 2021 fiscal year) — a different basis from the IMF calendar-year figures above. Do not mix the two series naively.
> 3. **Clean pre-treatment window is ~2011–2019** (2020 is COVID-confounded). That's ~9 usable years before treatment — workable for synthetic control, not luxurious.

---

## 2. The democratic government's forward plans

Two nested policy documents define what the civilian government was steering toward. In a "no-coup" scenario, these are your target trajectories.

### 2.1 Economic Policy of the Union of Myanmar (the "12-Point Economic Policy", July 2016)

The umbrella framework. **Vision:** people-centred, inclusive, continuous development supporting national reconciliation. **The 12 policies (paraphrased):**

1. Expand public finances via transparent, effective public financial management.
2. Reform/privatize State-owned enterprises where viable; promote SMEs as engines of jobs and growth.
3. Build human capital; expand vocational education and training.
4. Prioritize core infrastructure — electricity, roads, ports — plus a **data ID system, digital-government strategy, and e-government**.
5. Create jobs (incl. for returning migrants); favor high-employment enterprises short-term.
6. Balance agriculture and industry for food security and higher exports.
7. Protect economic freedom and private-sector/market growth; specific policies to raise foreign investment; strengthen property rights and rule of law.
8. Achieve financial stability supporting households, farmers, businesses long-term.
9. Build environmentally sustainable cities; upgrade public services and utilities; protect cultural heritage.
10. Establish a fair, efficient tax system; protect individual and property rights via law.
11. **Build IP-rights systems to encourage innovation and advanced technology.**
12. Position Myanmar's businesses to exploit ASEAN and global opportunities.

### 2.2 Myanmar Sustainable Development Plan (MSDP) 2018–2030

The operational plan built to align with the 12-Point Policy and the UN SDGs. Structure: **3 Pillars, 5 Goals, 28 Strategies, 251 Action Plans.**

| Pillar | Goal | Focus |
|--------|------|-------|
| **1. Peace & Stability** | Goal 1 | Peace, national reconciliation, security, good governance |
| | Goal 2 | Economic stability & strengthened macroeconomic management |
| **2. Prosperity & Partnership** | Goal 3 | Job creation & private-sector-led growth |
| **3. People & Planet** | Goal 4 | Human resources & social development for a 21st-century society |
| | Goal 5 | Natural resources & environment |

**Strategies under Goal 3 (the growth/innovation engine):** enabling environment for a diverse economy; SME-driven job creation; investment-friendly environment (ease of doing business); trade reform & regional integration; financial-services access; priority infrastructure; **and Strategy 3.7 — creativity & innovation.**

### 2.3 Innovation blueprint — MSDP Strategy 3.7 (maps directly to your "how innovative" question)

*"Encourage greater creativity and innovation which will contribute to the development of a modern economy."* The plan explicitly framed innovation as a way for Myanmar to **leapfrog into the 21st century**, and named these seven action plans:

- **3.7.1** — Develop a **National Innovation Policy**; strengthen legal/regulatory frameworks for innovation and entrepreneurship.
- **3.7.2** — Strengthen **academia ↔ research institute ↔ private sector** links (a national innovation ecosystem).
- **3.7.3** — Increase access to **R&D financing**.
- **3.7.4** — Help **startups** access finance and commercialize products/services.
- **3.7.5** — Support innovation and scientific research across all sectors.
- **3.7.6** — Strengthen **IP rights**, incl. a Myanmar **patent & trademark office**.
- **3.7.7** — Transition toward an **inclusive digital economy** — expand connectivity, online services, data literacy, with security/privacy.

(Lead ministries: Industry, Transport & Communications, Education, Commerce, Information. Tied to Economic Policy point 11 and SDG 9.5/9.b/9.c.)

---

## 3. Using this to calibrate the simulation

| Model component | Calibrate from |
|-----------------|----------------|
| **Pre-treatment outcome (synthetic control)** | §1 real GDP growth series, 2011–2019; plus poverty, FDI, mobile/internet series pulled live |
| **"No-coup" future path (system dynamics)** | MSDP intended trajectory to 2030 — high stability, continued liberalization, rising FDI |
| **Innovation / connectivity pillar** | Strategy 3.7 milestones as target states (National Innovation Policy enacted, patent office live, digital-economy transition) + the observed 2013–2020 connectivity leapfrog as the growth-rate prior |
| **Stability lever** | Pillar 1 / Goal 1 as the "high" setting; the coup as the drop |
| **Donor pool (synthetic Myanmar)** | Cambodia, Laos, Vietnam, Bangladesh, Nepal, Indonesia — exclude Sri Lanka (2022 crisis) |

The MSDP is mostly **qualitative** (action plans, not hard numeric 2030 targets), so treat it as **direction and milestones**, not as a set of published numbers. Numeric targets/trajectories should come from the live data sources below plus your own scenario assumptions.

---

## 4. Live data sources (for the hard numbers)

Pull time-series from these rather than scraping — cleaner and re-queryable:

- **World Bank WDI** — GDP, FDI, poverty, life expectancy, internet/mobile penetration, electrification. (Also exposed as an Alexandria provider `data-worldbank-org` via Firecrawl, if you'd rather fetch through that than hit the WB API directly.)
- **IMF World Economic Outlook** — GDP growth, inflation, debt (Alexandria provider `data-imf-org`, capability `datasets/weo`).
- **UNDP** — HDI components.
- **ACLED** — conflict intensity (essential for modelling the post-2021 divergence).

---

## Sources

- Myanmar Sustainable Development Plan (2018–2030), Ministry of Planning and Finance, Aug 2018 — via MIMU (themimu.info).
- Economic Policy of the Union of Myanmar (12-Point Policy), July 2016 — reproduced in the MSDP.
- World Bank, *Myanmar Country Overview* (worldbank.org) and *Myanmar Economic Monitor*.
- *Economy of Myanmar*, Wikipedia (macro-trends table; IMF-sourced).
