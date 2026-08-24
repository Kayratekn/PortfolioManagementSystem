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
| Latest fund price | Current valuation / price analytics | `DIRECT_TEFAS` | `fonGnlBlgSiraliGetir`; `fonFiyatBilgiGetir` | `fiyat`, `borsaBultenFiyat`, `tarih` | Direct value with endpoint-specific semantics | Latest available day | High | No | For the verified 2026-04-24 BYF cross-section, general-info `fiyat` behaved as calculated per-share fund value / NAV, while `borsaBultenFiyat` was the exchange-market price. `fonFiyatBilgiGetir.fiyat` matched `borsaBultenFiyat` in 30/30 BYF cases. Do not collapse these fields into one semantic meaning. |
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
| Fund category / subtype | Classification and filtering | `DIRECT_TEFAS` | Asset fund kind plus `fonProfilDtyGetir` | `Asset.fund_kind`; `fonProfilDtyGetir.fonTuru` | Direct metadata lookup / persisted type history | None | High | No | Production modeling uses `YAT` / `EMK` / `BYF` / `GYF` / `GSYF` as the main fund kind and `fonTuru` as the business-level fund-type classification. `fonTipiGetir` internal codes and `fonDetayGetir` / `fonUnvanGetir` auxiliary vocabularies are not used as a universal business subtype model. |
| 1-year category ranking | Relative 1-year performance rank within the fund category | `DIRECT_TEFAS` | TEFAS fund detail-analysis page | `kategoriDerece`, `kategoriFonSay` | Direct source values exposed as rank / category fund count | Current detail snapshot | High | No | TEFAS displays these values as its 1-year category ranking. `kategoriDerece` is the displayed rank and `kategoriFonSay` is the displayed category fund count. Zero or null source values must be preserved conservatively rather than interpreted as a valid rank. |
| Asset allocation | Exposure breakdown | `DIRECT_TEFAS` | `dagilimSiraliGetirT`; TEFAS asset-allocation UI | 54 observed allocation raw fields plus `tarih`; 43 fields have verified raw-to-UI label mappings | Direct allocation percentages for verified mapped fields | Latest available day | High | No | 43 of 54 raw allocation fields have verified same-date raw/UI mappings. The remaining 11 fields (`bb`, `db`, `dot`, `eut`, `fkb`, `kh`, `kks`, `t`, `vm`, `yba`, `ymk`) had no non-zero observation across 12,476 tested raw rows and remain preserved as unobserved/unused raw fields without guessed labels. |
| Founder / management company | Issuer/manager metadata | `NEEDS_VALIDATION` | Legacy `getFplFonList` observation only | Legacy `kurucuKod`, `kurucuAd` | Direct if a current source is re-verified | None | Low | Yes, if required | The legacy endpoint is not used as a current production contract. Re-verify a current authoritative source before exposing this metadata. |
| Operator | Operational entity metadata | `NEEDS_VALIDATION` | Legacy `getFplFonList` observation only | Legacy `oprKod`, `oprAd` | Direct if a current source is re-verified | None | Low | Yes, if required | Do not rely on the legacy endpoint for current production metadata. |
| Fund active/inactive status | Availability and lifecycle tracking | `NEEDS_VALIDATION` | Legacy `getFplFonList.durum` observation only | Legacy `durum` | Direct if a current source is re-verified | None | Low | Possibly | Current lifecycle-directory semantics require renewed source validation. Keep this separate from the implemented TEFAS platform-status field. |
| TEFAS performance comparison series | Relative performance context | `DIRECT_TEFAS` | `fonProfilDtyGetir` | `fonKodu`, `fonUnvan`, `fonTuru`, `fonTurGetiri` | Direct comparison-series output | Depends on endpoint period | High | No | Verified to be TEFAS performance-comparison series such as `ALTIN`, `BIST100`, `USD`, `TUFE`, and similar rows. These must not be treated as the fund's legally defined benchmark or threshold value; official benchmark disclosure requires a separately verified source such as KAP if needed. |
| Net fund flow / estimated money inflow-outflow | Capital movement estimate | `DERIVABLE_FROM_TEFAS` | `fonGnlBlgSiraliGetir` | `portfoyBuyukluk`, `fiyat`, `tarih`; `tedPaySayisi` can be used as a supporting cross-check | `current AUM - previous AUM * (current price / previous price)`, equivalent to removing the estimated valuation-return effect from the AUM change | At least 2 observations | Medium | No | This is an estimated net flow derived from TEFAS daily fund data, not a direct subscription/redemption transaction field. Raw investor cash-flow transactions remain unavailable in the verified TEFAS dataset. |

## Priority metrics for MVP

Conservative MVP candidates already supportable from verified TEFAS data:

- Latest fund price / price analytics with endpoint-specific `BYF` handling:
  general-info per-share fund value / NAV remains distinct from exchange bulletin
  price.
- Investor count.
- Investor count change and investor count growth %.
- Fund total value / AUM.
- AUM change and AUM growth %.
- Shares outstanding and shares outstanding change.
- Average fund value per investor.
- Historical return metrics calculated from `fonFiyatBilgiGetir`, beginning
  with daily, 5-day, 1-month, 3-month, 6-month, year-to-date, and 1-year return.
- Business-level fund classification from `Asset.fund_kind` and
  `fonProfilDtyGetir.fonTuru`.
- TEFAS performance-comparison series when comparison context is useful, while
  keeping them separate from a fund's legally defined benchmark.

Legacy founder/operator/lifecycle-directory metadata is not an MVP dependency
unless a current authoritative source is separately re-verified.

## Metrics requiring further validation

The remaining TEFAS metric issue that blocks production use of a custom derived
metric is:

- Fund market-share denominator grouping and the exact business definition of
  the relevant TEFAS comparison group.

Additional deferred source requirements are separate from the verified TEFAS
metric foundation:

- A legally defined official benchmark or threshold value requires a separately
  verified official source such as KAP if the product later requires it.
- Current founder / management company, operator, fund lifecycle status, and
  fund inception date require renewed source validation before use.

## Summary notes

- Site-observed labels such as `dailyReturn`, `marketShare`, `oneMonthReturn`,
  and similar keys are useful metric concepts, not automatically confirmed raw
  API fields.
- The matrix intentionally favors `DERIVABLE_FROM_TEFAS` over `DIRECT_TEFAS`
  when a metric can be safely computed from verified TEFAS raw data.
- BYF endpoint-specific price semantics are resolved for the verified
  `2026-04-24` cross-section and must remain represented by separate stored
  fields rather than a collapsed generic price meaning.
- `fonProfilDtyGetir` comparison rows are verified TEFAS performance-comparison
  series; they are not a substitute for the fund's legal benchmark.
- Production fund classification uses the backend fund kind plus
  `fonProfilDtyGetir.fonTuru`; provider-internal classification codes and
  auxiliary vocabularies do not need a separate business-domain model.
- Fund-market-share denominator grouping remains intentionally unresolved and
  should not be guessed.
