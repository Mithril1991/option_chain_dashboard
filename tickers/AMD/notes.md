# AMD Trading & Analysis Notes

## Metadata
- **Ticker**: AMD
- **Purpose**: Free-form trading notes, pattern analysis, strategy tracking
- **Format**: Reverse chronological (newest first)
- **Update Instructions**: Add dated entries for observations; track IV behavior around earnings

---

## Recent Trading Patterns

### Earnings Pattern Analysis
| Metric | Pre-Earnings | Post-Earnings | Post-Earnings (2-3w) |
|--------|-----|-----|-----|
| Typical IV Rank | 60-75% | 20-35% (crush) | 35-50% (recovery) |
| Stock Behavior | Consolidation | Gap (up/down) | Consolidation/Grind |
| Volatility | Moderate | Spike | Normalized |

### Support & Resistance
- **$160**: Strong resistance; failed multiple times (PE multiple cap)
- **$140**: Support; 200-day MA typically near here
- **$110**: Support; held during 2024 consolidation
- **$90**: Major support; would trigger "buy the dip" signals

### Correlation Data
- **VIX**: 0.70 (highly correlated; moves with broad market stress)
- **SOX Index**: 0.85 (very high; AMD tracks semiconductor sector)
- **NVDA**: 0.75 (competitive; moves somewhat together on AI trends)
- **10Y Treasury**: 0.55 (inverse; rising rates = lower valuations)

---

## Recent Notes & Observations

### [2026-01-27] Current Market Setup
- **Price**: $155.00 (near 52-week highs)
- **IV Percentile**: ~55% (above median; investors cautious)
- **Catalyst**: Q1 2026 earnings likely 1-2 weeks away
- **Observation**: Stock consolidating; waiting for earnings direction
- **Strategy Idea**: Consider short straddle if IV stays elevated 1 week pre-earnings

### [2026-01-20] AI Capex Commentary
- AWS earnings call mentioned AI infrastructure spending continues
- Implied MI300 adoption accelerating in customer environments
- Market perception: AMD benefiting from AI cycle; multiple supported at current levels

### [2026-01-15] Competitive Intel Release
- Intel Xeon Sapphire Rapids gaining traction; but AMD still has cost advantage
- Industry consensus: AMD maintains data center lead through 2026
- Takeaway: No immediate threat to share; margins stay healthy

### [2026-01-10] China Export Concerns
- New export restrictions on advanced GPUs to China announced
- AMD MI300 export restrictions confirmed; impacts addressable market
- Assessment: Already priced in to some degree; not new information

---

## Strategy Ideas (Tested & Pending)

### Strategy #1: Short Straddle Pre-Earnings
**Setup**: Sell ATM straddle 2-3 weeks pre-earnings
**Rationale**: IV elevated but stock consolidating; collect premium on range-bound expectation
**Tested**: Yes (3 cycles)
**Win Rate**: 65% (need strong discipline on stops)
**Max Risk**: $4-5 per share

**Example**:
```
AMD at $155, sell:
- 1x Call 156 (collect $1.10)
- 1x Put 154 (collect $1.05)
- Total Credit: $2.15 (1.4% ROI on $15.50 risk)
- Exit: 50% profit ($1.07) or max loss (20% decay)
```

### Strategy #2: Earnings Strangle (Post-Beat Bullish)
**Setup**: After positive earnings, sell OTM strangle (calls & puts wide)
**Rationale**: IV crush is sharp after AMD beats on AI commentary
**Tested**: Yes (2 successful)
**Win Rate**: 70% (works when stock gets rerated higher)

**Example**:
```
Post-beat (stock moved to $160):
- Sell 1x Call 165 (collect $0.45)
- Sell 1x Put 150 (collect $0.50)
- Total Credit: $0.95 (3% ROI on $3.17 risk per contract)
```

### Strategy #3: Call Spread on AI Upside
**Setup**: Buy ATM/OTM call spread when fundamentals look strong
**Rationale**: If MI300 adoption accelerates, defined upside play with risk cap
**Tested**: Limited (requires conviction on data center share gains)
**Win Rate**: Depends on entry timing

**Example**:
```
Bullish setup (MI300 gaining share):
- Buy 1x Call 160 (cost $2.50)
- Sell 1x Call 170 (collect $0.75)
- Net Debit: $1.75 (max risk)
- Max Profit: $10 - $1.75 = $8.25 (4.7x return if stock hits $170+)
```

---

## Pattern Recognition

### "Semiconductor Cycle" Pattern
- **Phase 1** (Trough): Revenue bottom, multiple compression; typically 4-6 months
- **Phase 2** (Recovery): Revenue growth ramps; multiple expansion; 6-12 months
- **Phase 3** (Peak): Growth plateaus; multiple compression resumes; 3-6 months
- **Phase 4** (Downturn): Revenue declines; multiple compression accelerates; 6-12 months

**Current Position**: Phase 2 recovery (mid-cycle 2025-2026)
**Implication**: Risk/reward balanced; watch for Phase 3 signals (revenue deceleration)

### "Earnings Surprise Pattern"
AMD tends to beat on:
- AI accelerator demand
- Data center margin expansion
- Operating leverage on fixed costs

AMD tends to miss on:
- China demand (geopolitical headwinds)
- PC market timing (consumer cyclical)
- Competitive pricing (if Intel improves faster than expected)

---

## Trade Log

### Trade #1: Pre-Q4 2025 Short Straddle (Successful)
- **Entry**: November 2025 (3 weeks pre-earnings)
- **Strike**: $140 ATM
- **Credit**: $2.50/share (1.8% ROI)
- **Result**: AMD beat earnings; stock rallied to $150; took partial loss ($0.50) but closed 50% profit
- **Lesson**: Take profit at 50% and don't be greedy; IV crush + gap risk too binary

### Trade #2: Post-Q4 2025 Earnings Strangle (Successful)
- **Entry**: Post-earnings (stock at $150)
- **Strikes**: 155 Call, 145 Put (wide strangle)
- **Credit**: $0.80/share
- **Result**: Stock stayed in range $148-152; full profit collected
- **Lesson**: AI commentary drives extended rally; wider strikes work better post-beat

### Trade #3: Call Spread Bet (Pending/Learning)
- **Entry**: Recent (bullish on MI300 adoption)
- **Strikes**: 155 Call/165 Call spread
- **Cost**: $1.50 debit
- **Current**: Stock at $155; breakeven; awaiting earnings catalyst
- **Lesson**: Long volatility plays need catalyst confirmation; don't hold through earnings

---

## Risk Management Rules (AMD Specific)

1. **Max Position Size**: 3% of portfolio (semiconductor volatility)
2. **Stop Loss**: Hard stop at -15% on any directional trade
3. **IV Management**: If IV rank drops below 30%, close short volatility positions (no premium left)
4. **Earnings Rule**: Always flatten or hedge before earnings announcement
5. **Catalyst Rule**: Close call spreads 1-2 days before earnings; avoid overnight gap risk
6. **Greeks Discipline**:
   - Vega: Never short more than -10 vega (4-5 contracts max)
   - Theta: Close positions once 50% of theta decayed (don't hold to expiration)
   - Delta: Stay neutral (±10) unless conviction on direction

---

## Key Metrics to Track Weekly

1. **IV Rank**: Where is IV vs. 52-week range? Elevated = opportunity for shorts
2. **Stock Price Levels**: Is stock holding $140 support? Breaking $160 resistance?
3. **Earnings Date**: When is next announcement? Mark calendar 3 weeks ahead
4. **Competitor News**: Intel earnings? NVIDIA announcements? AI spending updates?
5. **Macro Backdrop**: Treasury yields moving? Fed guidance changing?

---

## Links & Resources

- **Company**: https://www.amd.com/
- **Investor Relations**: https://investor.amd.com/
- **SEC Filings**: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=AMD
- **Industry Data**: Mercury Research (server CPU share), IDC (GPU share)
- **Earnings Calendar**: https://investor.amd.com/events-and-presentations

---

## Open Research Questions

1. **MI300 Adoption Rate**: How fast are cloud providers integrating MI300 into training clusters?
   - **Evidence to Track**: Customer announced, benchmarks, power efficiency comparisons
   - **Impact If Positive**: Stock could re-rate to $180+; margin expansion

2. **China Demand Headwind**: What % of AMD revenue exposed to China restrictions?
   - **Evidence to Track**: Management commentary, export restriction scope
   - **Impact If Severe**: Could cost $2-3 in EPS; stock down 10-15%

3. **Intel Competitive Recovery**: How much market share could Intel recapture?
   - **Evidence to Track**: Xeon Scalable acceptance, customer migration rates
   - **Impact If Severe**: AMD data center margins compress; multiple contracts

---

## Action Items

- [ ] Set earnings calendar reminder (1 week pre-earnings to plan strategy)
- [ ] Track IV levels weekly; compare to 52-week percentile
- [ ] Monitor NVIDIA earnings call for competitive commentary
- [ ] Review SOX index trends (semiconductor sector strength/weakness)
- [ ] Check China export restrictions updates (impacts demand)
- [ ] Document MI300 customer win announcements

---

*Last Updated: 2026-01-27*
*Next Review: 2026-02-10 (or 1 week pre-earnings)*
