# TEFAS Metric Matrix

Purpose: map candidate fund and portfolio metrics to verified TEFAS sources,
conservative derivation paths, and unresolved dependencies.

Availability classifications used in this document:

- `DIRECT_TEFAS`
- `DERIVABLE_FROM_TEFAS`
- `NEEDS_VALIDATION`
- `EXTERNAL_SOURCE_REQUIRED`

## Metric decision matrix

| Metric | Business purpose | Availability classification | Verified TEFAS source | Required raw fields | Calculation / derivation | Required history window | Confidence | External source needed? | Notes / unresolved issues |
|---|---|---|---|---|---|---|---|---|---|
| Latest fund price | Current valuation | `DIRECT_TEFAS` | `fonGnlBlgSiraliGetir`; `fonFiyatBilgiGetir` | `fiyat`, `borsaBultenFiyat`, `tarih` | Direct latest value per endpoint | Latest available day | Medium | No | For `BYF`, `BLH` showed `fonGnlBlgSiraliGetir.fiyat = 49.222014` but `fonFiyatBilgiGetir.fiyat = 49.24`, matching `borsaBultenFiyat`; endpoint-specific price semantics must not be assumed identical. |
| Daily return | Short-term performance | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir`; site label `dailyReturn` | `fiyat`, `tarih` | `(current fiyat / previous available fiyat) - 1` | Previous available trading/data day | Medium | No | Site describes daily return as percentage change in fund prices; treat site label as concept, not confirmed raw field. |
| 5-day return | Weekly momentum | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir` | `fiyat`, `tarih` | Return between current observation and the 5th previous available observation | Approximately 6 price observations | Medium | No | An exact 5-available-day return requires the current observation plus the 5th previous available observation; use available TEFAS observations, not calendar days. |
| 1-month return | Monthly performance | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir`; site label `oneMonthReturn` | `fiyat`, `tarih` | Return between latest and approximately 1 month earlier | About 1 month | Medium | No | Prefer self-calculation until direct endpoint semantics are validated. |
| 3-month return | Quarterly performance | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir`; site label `threeMonthReturn` | `fiyat`, `tarih` | Return between latest and approximately 3 months earlier | About 3 months | Medium | No | Same conservative approach as 1-month return. |
| 6-month return | Medium-term performance | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir`; site label `sixMonthReturn` | `fiyat`, `tarih` | Return between latest and approximately 6 months earlier | About 6 months | Medium | No | Same conservative approach as other period returns. |
| Year-to-date return | Current-year performance | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir`; site label `yearToDateReturn` | `fiyat`, `tarih` | Return between latest and first available observation in current year | Year start to latest | Medium | No | Use first available TEFAS observation in year if year-start date is not a trading day. |
| 1-year return | Annual performance | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir`; site label `oneYearReturn` | `fiyat`, `tarih` | Return between latest and approximately 1 year earlier | About 1 year | Medium | No | Site notes period returns use start/end reported prices. |
| 3-year return | Long-term performance | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir`; site label `threeYearReturn` | `fiyat`, `tarih` | Return between latest and approximately 3 years earlier | About 3 years | Low | No | Depends on TEFAS price history depth for each fund. |
| 5-year return | Long-term performance | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir`; site label `fiveYearReturn` | `fiyat`, `tarih` | Return between latest and approximately 5 years earlier | About 5 years | Low | No | Depends on TEFAS price history depth for each fund. |
| Investor count | Participation breadth | `DIRECT_TEFAS` | `fonGnlBlgSiraliGetir`; site label `investorCount` | `kisiSayisi`, `tarih` | Direct latest value | Latest available day | High | No | Site description aligns with observed raw field label. |
| Investor count change | Trend in participation | `DERIVABLE_FROM_TEFAS` | `fonGnlBlgSiraliGetir` | `kisiSayisi`, `tarih` | `current kisiSayisi - previous kisiSayisi` | At least 2 observations | High | No | Requires historical snapshots from TEFAS general info. |
| Investor count growth % | Participation growth rate | `DERIVABLE_FROM_TEFAS` | `fonGnlBlgSiraliGetir` | `kisiSayisi`, `tarih` | `(current / previous) - 1` | At least 2 observations | High | No | Null/zero prior-count handling required. |
| Fund total value / AUM | Fund size | `DIRECT_TEFAS` | `fonGnlBlgSiraliGetir`; site label `fundTotalValue` | `portfoyBuyukluk`, `tarih` | Direct latest value | Latest available day | High | No | `portfoyBuyukluk` is the verified raw field currently used as fund total value / AUM proxy. |
| AUM change | Size trend | `DERIVABLE_FROM_TEFAS` | `fonGnlBlgSiraliGetir` | `portfoyBuyukluk`, `tarih` | `current portfoyBuyukluk - previous portfoyBuyukluk` | At least 2 observations | High | No | Requires historical TEFAS snapshots. |
| AUM growth % | Size growth rate | `DERIVABLE_FROM_TEFAS` | `fonGnlBlgSiraliGetir` | `portfoyBuyukluk`, `tarih` | `(current / previous) - 1` | At least 2 observations | High | No | Null/zero prior-AUM handling required. |
| Average fund value per investor | Fund size normalized by investor base | `DERIVABLE_FROM_TEFAS` | `fonGnlBlgSiraliGetir` | `portfoyBuyukluk`, `kisiSayisi`, `tarih` | `portfoyBuyukluk / kisiSayisi` | Latest available day | High | No | Must handle null and division-by-zero cases conservatively. |
| Fund market share | Share within fund type | `NEEDS_VALIDATION` | `fonGnlBlgSiraliGetir`; site label `marketShare` | `portfoyBuyukluk`, `tarih` plus all funds in relevant type/day | `fund portfoyBuyukluk / total portfoyBuyukluk of relevant fund type` | Same-day cross-section | Medium | No | TEFAS provides the formula concept, but the exact business mapping of "relevant type" to discovered TEFAS classification structures must be validated before production use. |
| Shares outstanding | Ownership base size | `DIRECT_TEFAS` | `fonGnlBlgSiraliGetir`; site label `fundShares` | `tedPaySayisi`, `tarih` | Direct latest value | Latest available day | High | No | Treat as direct TEFAS field. |
| Shares outstanding change | Ownership base trend | `DERIVABLE_FROM_TEFAS` | `fonGnlBlgSiraliGetir` | `tedPaySayisi`, `tarih` | `current tedPaySayisi - previous tedPaySayisi` | At least 2 observations | High | No | Requires historical snapshots. |
| Historical volatility | Risk estimate from price variability | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir` | `fiyat`, `tarih` | Statistical volatility on historical return series | Depends on chosen model; conservatively about 1-12 months | Medium | No | Derived from historical prices, not a direct TEFAS raw field. |
| Maximum drawdown | Peak-to-trough downside | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir` | `fiyat`, `tarih` | Worst cumulative drop from prior peak | Depends on chosen window; conservatively about 6-12 months or longer | Medium | No | Derived from historical prices, not direct TEFAS output. |
| Rolling returns | Time-series performance windows | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir` | `fiyat`, `tarih` | Repeated return calculation over moving windows | Depends on chosen window | Medium | No | Derived from historical prices. |
| Momentum | Relative trend signal | `DERIVABLE_FROM_TEFAS` | `fonFiyatBilgiGetir` | `fiyat`, `tarih` | High-level trend score from recent returns or price path | Depends on chosen definition; conservatively about 1-12 months | Low | No | Requires explicit product definition before production use. |
| Fund category / subtype | Classification and filtering | `DIRECT_TEFAS` | `fonDetayGetir`; `fonUnvanGetir` | `fonTipi`, `fonTurKod`, `fonTurAciklama`, `tanim` | Direct metadata lookup | None | Medium | No | Multiple classification endpoints exist; exact business mapping between them still needs careful modeling. |
| Category ranking | Relative ranking within type | `NEEDS_VALIDATION` | `fonFiyatBilgiGetir`; site label `fundCategoryDegree` | `kategoriDerece`, `kategoriFonSay`, possibly `fiyat`, `tarih` | Likely ranking-style metric, but semantics not confirmed | Unknown | Low | No | Discovery notes explicitly leave `kategoriDerece`, `kategoriFonSay`, and ranking semantics unresolved. |
| Asset allocation | Exposure breakdown | `NEEDS_VALIDATION` | `dagilimSiraliGetirT`; site note on Takasbank allocation | Raw fields such as `bb`, `bpp`, `gsykb`, `vdm`, etc.; `tarih` | Requires mapping of abbreviated raw fields to business categories | Latest available day | Low | No | Raw allocation fields are verified, but their meanings are unresolved. |
| Founder / management company | Issuer/manager metadata | `DIRECT_TEFAS` | `getFplFonList` | `kurucuKod`, `kurucuAd` | Direct metadata lookup | None | High | No | Useful for asset master/directory data. |
| Operator | Operational entity metadata | `DIRECT_TEFAS` | `getFplFonList` | `oprKod`, `oprAd` | Direct metadata lookup | None | High | No | Useful for asset master/directory data. |
| Fund active/inactive status | Availability and lifecycle tracking | `DIRECT_TEFAS` | `getFplFonList` | `durum` | Direct metadata lookup | None | Medium | No | `durum` is observed; exact allowed values still need enumeration. |
| Benchmark comparison | Relative performance context | `NEEDS_VALIDATION` | `fonProfilDtyGetir` | `fonKodu`, `fonUnvan`, `fonTuru`, `fonTurGetiri` | Use returned comparison/benchmark series such as `ALTIN`, `BIST100`, `USD` | Depends on endpoint period | Medium | No | Endpoint clearly returns comparison data, but exact row/series semantics need further modeling. |
| Net fund flow / estimated money inflow-outflow | Capital movement estimate | `NEEDS_VALIDATION` | `fonGnlBlgSiraliGetir` | `portfoyBuyukluk`, `tedPaySayisi`, `fiyat`, `tarih` | Methodology using value, price, and/or share-count changes must be validated before production use | At least 2 observations | Low | No | Do not treat as reliably calculable yet. Appropriate methodology remains unresolved. |

## Priority metrics for MVP

Conservative MVP candidates already supportable from verified TEFAS data:

- Latest fund price, with endpoint-specific handling notes for `BYF`.
- Investor count.
- Investor count change and investor count growth %.
- Fund total value / AUM.
- AUM change and AUM growth %.
- Shares outstanding and shares outstanding change.
- Average fund value per investor.
- Founder / management company.
- Operator.
- Fund active/inactive status.
- Historical return metrics calculated from `fonFiyatBilgiGetir`, beginning with daily, 5-day, 1-month, 3-month, 6-month, year-to-date, and 1-year return.

## Metrics requiring further validation

Minimum set requiring further validation before production use:

- Net fund flow / estimated money inflow-outflow.
- Category ranking and the semantics of `kategoriDerece` and `kategoriFonSay`.
- Asset allocation category meanings for abbreviated `dagilimSiraliGetirT` fields.
- Benchmark comparison row/series semantics from `fonProfilDtyGetir`.
- Fund market share denominator grouping and the business mapping of the relevant type.
- Cross-endpoint price semantics, especially for `BYF`, where `fiyat` did not match across verified observations on `2026-04-24`.
- Detailed classification mapping across `fonDetayGetir`, `fonUnvanGetir`, and `fonTipiGetir`.

## Summary notes

- Site-observed labels such as `dailyReturn`, `marketShare`, `oneMonthReturn`, and similar keys are useful metric concepts, not automatically confirmed raw API fields.
- The matrix intentionally favors `DERIVABLE_FROM_TEFAS` over `DIRECT_TEFAS` when a metric can be safely computed from verified TEFAS raw data without relying on unresolved endpoint semantics.
- No metric in this matrix currently requires a confirmed external source based on the verified TEFAS evidence alone, but some metrics remain unsuitable for production until their TEFAS semantics are validated.
