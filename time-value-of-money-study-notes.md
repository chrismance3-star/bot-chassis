# Time Value of Money: Questions, Answers, and Worked Solutions

## Formula sheet

| Concept | Formula |
|---|---|
| Future value (lump sum) | FV = PV × (1 + r)ⁿ |
| Present value (lump sum) | PV = FV / (1 + r)ⁿ |
| Solve for rate | r = (FV / PV)^(1/n) − 1 |
| Solve for time | n = ln(FV / PV) / ln(1 + r) |
| EAR (periodic compounding) | EAR = (1 + APR/m)ᵐ − 1 |
| EAR (continuous) | EAR = e^APR − 1 |
| FV of ordinary annuity | FV = PMT × [(1 + r)ⁿ − 1] / r |
| PV of ordinary annuity | PV = PMT × [1 − (1 + r)⁻ⁿ] / r |
| Loan payment | PMT = PV × r / [1 − (1 + r)⁻ⁿ] |
| Savings payment for a goal | PMT = FV × r / [(1 + r)ⁿ − 1] |
| Perpetuity | PV = C / r |
| Periods to pay off a balance | n = −ln(1 − r·PV/PMT) / ln(1 + r) |

Conventions:
- For monthly compounding, r = APR / 12 and n = years × 12.
- "End of each period" means ordinary annuity.
- APR is the stated rate. EAR is the true annual rate after compounding.

---

## Questions and answers

### Q1. Mortgage payment: **$1,572.26**
$350,000 house, 20% down, 30-year fixed at 5.4% APR compounded monthly.
1. Loan = 350,000 × 0.80 = $280,000
2. r = 0.054 / 12 = 0.0045, n = 360
3. PMT = 280,000 × 0.0045 / (1 − 1.0045⁻³⁶⁰) = 1,260 / 0.80138 = **$1,572.26**

### Q2. Time to triple at 7.5%: **15.19 years**
t = ln 3 / ln 1.075 = 1.0986 / 0.07232 = **15.19**

### Q3. Compounding frequencies: **"For a given APR, the EAR increases as compounding frequency increases."**
- EAR rises with m and approaches e^APR − 1 as m goes to infinity.
- Frequency does affect future value.
- APR is at most the EAR, equal only with annual compounding.
- Continuous compounding gives the highest EAR, not the lowest.

### Q4. Credit card payoff: **93.11 months**
$2,000 balance, 1.5% per month, $40 payment.
1. r·PV/PMT = 0.015 × 2000 / 40 = 0.75
2. n = −ln(0.25) / ln(1.015) = 1.3863 / 0.014889 = **93.11**

### Q5. Time to double at 6%: **11.90 years**
t = ln 2 / ln 1.06 = 0.6931 / 0.05827 = **11.90**. The $5,000 is irrelevant.

### Q6. PV of $300/month for 4 years at 6% APR monthly: **$12,774.10**
r = 0.005, n = 48. PV = 300 × (1 − 1.005⁻⁴⁸) / 0.005 = 300 × 42.580 = **$12,774.10**

### Q7. $100/month at 9% APR monthly for 35 years: **$294,510.23** (exact math gives $294,178.45)
r = 0.0075, n = 420.
1. 1.0075⁴²⁰ = 23.0634
2. (23.0634 − 1) / 0.0075 = 2,941.78
3. × 100 = $294,178.45. Pick the closest option, $294,510.23. The gap is key rounding.
- Total deposits are $42,000. About $252,000 is interest.

### Q8. EAR of 12% APR monthly: **12.68%**
EAR = 1.01¹² − 1 = 0.12683

### Q9. $25,000 car loan, 5 years, 6% APR monthly: **$483.32**
r = 0.005, n = 60.
1. 1.005⁻⁶⁰ = 0.74137, so the denominator is 1 − 0.74137 = 0.25863
2. PMT = 125 / 0.25863 = **$483.32**
- Total paid is about $29,000, so interest is about $4,000.

### Q10. Preferred stock, $4.50 dividend, 9% required return: **$50.00**
P = D / r = 4.50 / 0.09

### Q11. $2,000 at end of each year for 30 years at 9%: **$272,615.08**
1.09³⁰ = 13.2677. FV = 2,000 × (13.2677 − 1) / 0.09 = 2,000 × 136.31 = **$272,615**

### Q12. Sweepstakes, $50,000 per year for 20 years at 6%, first payment in one year: **$573,496.06**
PV = 50,000 × (1 − 1.06⁻²⁰) / 0.06 = 50,000 × 11.4699 = **$573,496**. It is an ordinary annuity, so there is no adjustment.

### Q13. EAR of 9% compounded continuously: **9.42%**
e^0.09 − 1 = 0.09417

### Q14. Indifference rate, $10,000 now vs $15,000 in 5 years: **8.45%**
(1 + r)⁵ = 1.5, so r = 1.5^(0.2) − 1 = 1.08447 − 1 = **8.45%**

### Q15. Deposit today for $10,000 in 4 years at 8%: **$7,350.30**
PV = 10,000 / 1.08⁴ = 10,000 / 1.36049

### Q16. PV of $4,000 in 2 years and $6,000 in 5 years at 8%: **$7,512.85**
4,000 / 1.1664 = 3,429.36. 6,000 / 1.46933 = 4,083.50. Sum = **$7,512.85**.
Discount each cash flow separately, then add.

### Q17. Higher discount rate, present value: **It decreases.**
PV = FV / (1 + r)ⁿ. A larger r makes the denominator bigger, for any n.

### Q18. $2,000 at 6% for 5 years: **$2,676.45**
2,000 × 1.06⁵ = 2,000 × 1.338226

### Q19. Grandson's account, $2,000 to $4,317.85 in 10 years: **8.00%**
1. Growth multiple = 4,317.85 / 2,000 = 2.15893. This is the cumulative 10-year growth, so each $1 became $2.15893.
2. Take the 10th root: 2.15893^(1/10) = 1.08. With logs: ln(2.15893) = 0.76961, divided by 10 is 0.076961, and e^0.076961 = 1.08.
3. r = 1.08 − 1 = **8.00%**
4. Check: 1.08¹⁰ = 2.15893.
- Common mistake: dividing total growth by years (115.9% / 10 = 11.6%). That ignores compounding.

### Q20. Save for $1,000,000 in 40 years at 8%, end-of-year deposits: **$3,860.16**
1.08⁴⁰ = 21.7245. PMT = 1,000,000 × 0.08 / (21.7245 − 1) = 80,000 / 20.7245 = **$3,860.16**

---

## Patterns to recognize

1. **Single lump sum vs a stream of equal payments.** Lump sum uses FV or PV of (1 + r)ⁿ. A stream uses an annuity formula.
2. **FV annuity vs PV annuity.** Saving toward a goal uses the FV annuity (Q7, Q11, Q20). Borrowing or valuing payments today uses the PV annuity (Q1, Q6, Q9, Q12).
3. **Match r and n to the payment frequency.** Monthly payments need a monthly rate and months.
4. **Unknown rate or time.** Isolate (1 + r)ⁿ, then use a root for r or logs for n (Q2, Q4, Q5, Q14, Q19).
5. **APR vs EAR.** Compounding more often raises EAR (Q3, Q8, Q13).
6. **Answer-key rounding.** If an option is within about 0.1% of your exact answer, it is probably the intended one (Q7).
