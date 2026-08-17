# TEFAS External Data Gap Analysis

Purpose: identify which important fund attributes are already covered by
verified TEFAS data, which are only site-visible so far, which are derivable,
and which may require another source after TEFAS validation is exhausted.

Availability classifications used in this document:

- `VERIFIED_TEFAS_STRUCTURED`
- `DERIVABLE_FROM_TEFAS`
- `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION`
- `NEEDS_SOURCE_RESEARCH`
- `EXTERNAL_SOURCE_CANDIDATE`

## Attribute gap matrix

| Attribute | Why useful | Classification | Current TEFAS evidence | Verified raw field / endpoint if available | Can it be derived? | External source candidate | Priority | Notes / unresolved issue |
|---|---|---|---|---|---|---|---|---|
| ISIN code | External identifier, cross-system matching | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts | None verified yet | No | None yet | High | Site-visible, but no verified structured extraction path yet. |
| Fund risk value / risk score | Risk disclosure and filtering | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Confirmed on the official TEFAS fund detail-analysis page as a direct 1-7 fund risk value | No backend extraction path implemented yet | No | None | High | TEFAS itself provides the official current risk value, so an external source is not currently required. Backend extraction and normalization still need implementation; missing source values should remain null rather than being replaced with a derived volatility score. |
| Fund category | Classification, filtering, grouping | `VERIFIED_TEFAS_STRUCTURED` | Verified endpoint observations | `fonDetayGetir`: `fonTipi`, `fonTurKod`, `fonTurAciklama`; `fonUnvanGetir`: `tanim` | No | None | High | Multiple TEFAS classification structures exist; mapping between them still needs careful modeling. |
| Fund subtype | Classification, filtering, grouping | `VERIFIED_TEFAS_STRUCTURED` | Verified endpoint observations | `fonDetayGetir`: `fonTipi`, `fonTurKod`, `fonTurAciklama` | No | None | High | Structured metadata exists, but business interpretation must still stay conservative. |
| Founder / management company | Ownership/manager metadata | `VERIFIED_TEFAS_STRUCTURED` | Verified endpoint observations | `getFplFonList`: `kurucuKod`, `kurucuAd` | No | None | High | Already verified as structured TEFAS directory data. |
| Operator | Operational entity metadata | `VERIFIED_TEFAS_STRUCTURED` | Verified endpoint observations | `getFplFonList`: `oprKod`, `oprAd` | No | None | Medium | Already verified as structured TEFAS directory data. |
| Fund active/inactive status | Lifecycle/status filtering | `VERIFIED_TEFAS_STRUCTURED` | Verified endpoint observations | `getFplFonList`: `durum` | No | None | High | Allowed status values still need enumeration. |
| Platform status | Whether the fund is available/operational on platform | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts | None verified yet | No | None yet | Medium | Distinct from verified `durum` until proven otherwise. |
| Purchase settlement / buy value date | Trading operations, liquidity expectations | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts; TEFAS FAQ points users to KAP for settlement/value-date info | None verified yet | No | KAP | High | Keep as TEFAS site-visible for now; KAP is an official external-source candidate if TEFAS structured extraction is not validated. |
| Sale settlement / sell value date | Trading operations, liquidity expectations | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts; TEFAS FAQ points users to KAP for settlement/value-date info | None verified yet | No | KAP | High | Same handling as purchase settlement. |
| Transaction start time | Order-window operations | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts | None verified yet | No | None yet | Medium | Site-visible, but no verified structured path yet. |
| Transaction end time | Order-window operations | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts | None verified yet | No | None yet | Medium | Site-visible, but no verified structured path yet. |
| Entrance commission | Cost disclosure | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts | None verified yet | No | None yet | Medium | Site-visible, but no verified structured extraction path yet. |
| Exit commission | Cost disclosure | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts | None verified yet | No | None yet | Medium | Site-visible, but no verified structured extraction path yet. |
| Interest-content information | Compliance/product screening | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts | None verified yet | No | None yet | Medium | Site-visible, but no verified structured extraction path yet. |
| Management fee / fund management fee | Cost disclosure, net-return analysis | `NEEDS_SOURCE_RESEARCH` | No verified evidence in current TEFAS discovery | None verified | No | None yet | High | Do not assume current TEFAS support without verified evidence. |
| Benchmark | Relative-performance context, disclosures | `NEEDS_SOURCE_RESEARCH` | `fonProfilDtyGetir` returns comparison series, but official benchmark semantics are not verified | `fonProfilDtyGetir`: `fonKodu`, `fonUnvan`, `fonTuru`, `fonTurGetiri` | No | KAP may be relevant if official benchmark disclosure is required | Medium | Comparison series must not be automatically equated with the fund's legally defined benchmark. |
| Fund inception / start date | Lifecycle analytics, age filtering | `NEEDS_SOURCE_RESEARCH` | `getFplFonList.tarih` exists, but meaning is unresolved | `getFplFonList`: `tarih` | No | None yet | Medium | Do not assume `tarih` is inception date. |
| Currency | Valuation, display, reporting | `VERIFIED_TEFAS_STRUCTURED` | Verified currency lookup request | `v2` lookup: `dovizKod`, `dovizAd` | No | None | High | Verified auxiliary TEFAS currency metadata exists. |
| Fund total value | AUM, size, market-share denominator candidate | `VERIFIED_TEFAS_STRUCTURED` | Verified general-info endpoint; site metric concept `fundTotalValue` | `fonGnlBlgSiraliGetir`: `portfoyBuyukluk`, `tarih` | No | None | High | Verified raw TEFAS field exists. |
| Investor count | Participation breadth | `VERIFIED_TEFAS_STRUCTURED` | Verified general-info endpoint; site metric concept `investorCount` | `fonGnlBlgSiraliGetir`: `kisiSayisi`, `tarih` | No | None | High | Verified raw TEFAS field exists. |
| Shares outstanding | Ownership base size | `VERIFIED_TEFAS_STRUCTURED` | Verified general-info endpoint; site metric concept `fundShares` | `fonGnlBlgSiraliGetir`: `tedPaySayisi`, `tarih` | No | None | High | Verified raw TEFAS field exists. |
| Asset allocation | Portfolio exposure analysis | `VERIFIED_TEFAS_STRUCTURED` | Verified `dagilimSiraliGetirT` endpoint plus same-date TEFAS UI validation | `dagilimSiraliGetirT`: 54 observed allocation raw fields plus metadata; 43 raw fields have verified business-label mappings | No derivation required for verified mapped fields | None | High | 43 of 54 allocation fields have verified same-date raw/UI mappings. The remaining 11 fields (`bb`, `db`, `dot`, `eut`, `fkb`, `kh`, `kks`, `t`, `vm`, `yba`, `ymk`) remained null/zero across 12,476 tested raw rows and are preserved as unobserved/unused raw fields without guessed labels. |
| Historical price | Performance and risk analytics base series | `VERIFIED_TEFAS_STRUCTURED` | Verified historical-price endpoint | `fonFiyatBilgiGetir`: `fonKodu`, `fonUnvan`, `kategoriDerece`, `kategoriFonSay`, `tarih`, `fiyat` | No | None | High | For `BYF`, `fiyat` semantics differ from `fonGnlBlgSiraliGetir.fiyat` in the verified `BLH` observation. |
| Historical returns | Performance metrics over time | `DERIVABLE_FROM_TEFAS` | Metric matrix confirms derivation from verified historical prices; site exposes return concepts | Primarily `fonFiyatBilgiGetir`: `fiyat`, `tarih` | Yes | None | High | Daily, 5-day, 1-month, 3-month, 6-month, YTD, 1-year and longer-window returns can be derived conservatively from price history. |
| Estimated net fund flow / inflow-outflow | Short-term capital movement analysis | `DERIVABLE_FROM_TEFAS` | Verified TEFAS daily AUM and price data; derivation methodology documented in the metric matrix | `fonGnlBlgSiraliGetir`: `portfoyBuyukluk`, `fiyat`, `tarih`; `tedPaySayisi` can support cross-checking | Yes | None | High | Derived as `current AUM - previous AUM * (current price / previous price)`. This is an estimated net flow rather than a direct subscription/redemption transaction field; raw investor cash-flow transactions remain unavailable in the verified TEFAS dataset. |
| 1-year category ranking | Relative 1-year performance rank within the fund category | `VERIFIED_TEFAS_STRUCTURED` | Verified structured data extracted from the TEFAS fund detail-analysis page | Fund detail `bilgi_data`: `kategoriDerece`, `kategoriFonSay` | No | None | High | TEFAS exposes the current 1-year category rank and category fund count directly. The backend already extracts and stores both values. Zero or null source values are preserved conservatively and are not interpreted as valid ranks. |

## Recommended external-source investigation order

1. TEFAS as the primary source for daily fund data and validated site/detail data.
2. KAP as the preferred official supplementary source when a required disclosure or granular fund document is not available through TEFAS.
3. FVT only as a reference, cross-check, or product-analysis inspiration source; do not make it a required backend data dependency for the current MVP.

## Likely MVP external-data needs

No external source is currently required for the core MVP fund-data
capabilities. Verified TEFAS data covers fund total value, investor count,
shares outstanding, historical price, founder/management company, operator,
category/subtype metadata, active/inactive status, 1-year category ranking,
and the verified asset-allocation mappings. Historical returns and estimated
net fund flow can be derived from verified TEFAS daily data.

The official current fund risk value is also available on the TEFAS
detail-analysis page, so it does not currently justify an external data
dependency; backend extraction and normalization still need implementation.

KAP remains the preferred official supplementary source when a required
disclosure, settlement/value-date field, or more granular fund document cannot
be reliably obtained from TEFAS.

FVT is not required as a backend data dependency for the current MVP. It may be
used only as a reference, cross-check, or product-analysis inspiration source.

## Questions still requiring discovery

- Is there a stable structured TEFAS extraction path for site-visible fields such as ISIN, platform status, transaction times, commissions, and interest-content information?
- What is the exact business mapping between `fonDetayGetir`, `fonUnvanGetir`, and `fonTipiGetir` classification structures?
- Is there a verified TEFAS structured source for management fee?
- Does TEFAS expose an official benchmark field anywhere, or only comparison series through `fonProfilDtyGetir`?
- What is the exact meaning of `getFplFonList.tarih`?
- Can settlement/value-date information be reliably extracted from TEFAS, or should KAP be treated as the primary official source?
- Which TEFAS price field should be treated as authoritative for `BYF` and possibly other fund types when endpoint semantics differ?

## Summary view

Already covered by verified TEFAS structured data:

- Fund category.
- Fund subtype.
- Founder / management company.
- Operator.
- Fund active/inactive status.
- Currency.
- Fund total value.
- Investor count.
- Shares outstanding.
- Historical price.
- Asset allocation (43 verified mappings; 11 unobserved raw fields preserved).
- 1-year category ranking.

Available from verified TEFAS derivation:

- Historical returns.
- Estimated net fund flow / inflow-outflow.

Not yet proven as structured, but visible on the TEFAS site:

- ISIN code.
- Fund risk value / risk score.
- Platform status.
- Purchase settlement / buy value date.
- Sale settlement / sell value date.
- Transaction start time.
- Transaction end time.
- Entrance commission.
- Exit commission.
- Interest-content information.

Still needing source research:

- Management fee / fund management fee.
- Official benchmark.
- Fund inception / start date.
