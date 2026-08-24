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
| ISIN code | External identifier, cross-system matching | `VERIFIED_TEFAS_STRUCTURED` | Verified extraction from the TEFAS fund detail-analysis page and Asset-level opportunistic persistence/enrichment | TEFAS detail-page `profilData`; normalized backend ISIN extraction | No | None | High | Extraction and persistence are implemented. A separate whole-universe ISIN backfill is intentionally not part of the daily bulk sync. |
| Fund risk value / risk score | Risk disclosure and filtering | `VERIFIED_TEFAS_STRUCTURED` | Verified official TEFAS fund detail-analysis value | Fund detail `profilData["riskDegeri"]` | No | None | High | Backend extraction, 1..7 validation and detail-snapshot persistence are implemented. Missing source values remain null and are not replaced with derived volatility. |
| Fund category | Classification, filtering, grouping | `VERIFIED_TEFAS_STRUCTURED` | Verified TEFAS fund-kind and profile-type observations | `Asset.fund_kind`; `fonProfilDtyGetir.fonTuru` | No | None | High | The backend keeps `YAT` / `EMK` / `BYF` / `GYF` / `GSYF` as the main fund kind and persists `fonTuru` as business-level fund-type history. Provider-internal `fonTipiGetir` codes are not used as user-facing categories. |
| Fund subtype | Classification, filtering, grouping | `VERIFIED_TEFAS_STRUCTURED` | Verified profile-level TEFAS classification | `fonProfilDtyGetir`: `fonTuru` | No | None | High | `fonTuru` is the production business-level classification source. `fonDetayGetir` and `fonUnvanGetir` expose auxiliary vocabularies but are not modeled as a universal subtype master. |
| Founder / management company | Ownership/manager metadata | `NEEDS_SOURCE_RESEARCH` | Legacy `getFplFonList` observations contained founder fields, but the endpoint is not used as a current production source | Legacy `getFplFonList`: `kurucuKod`, `kurucuAd` | No | KAP may be relevant if required | Medium | Do not treat the legacy endpoint as a current authoritative production source. Re-verify a current source if this metadata becomes an MVP requirement. |
| Operator | Operational entity metadata | `NEEDS_SOURCE_RESEARCH` | Legacy `getFplFonList` observations contained operator fields, but the endpoint is not used as a current production source | Legacy `getFplFonList`: `oprKod`, `oprAd` | No | KAP may be relevant if required | Low | Re-verify a current source before production use. |
| Fund active/inactive status | Lifecycle/status filtering | `NEEDS_SOURCE_RESEARCH` | Legacy `getFplFonList.durum` was observed historically, but it is not a current production source | Legacy `getFplFonList`: `durum` | No | None yet | Medium | Do not rely on the legacy directory field for current lifecycle state without renewed source validation. This is distinct from the implemented TEFAS platform-status metadata. |
| Platform status | Whether the fund is available/operational on the TEFAS platform | `VERIFIED_TEFAS_STRUCTURED` | Verified TEFAS detail-page `profilData` extraction | Detail-page profile metadata persisted as `tefas_status` | No | None | Medium | Extraction and nullable detail-snapshot persistence are implemented. Keep platform status distinct from legacy fund lifecycle/directory status. |
| Purchase settlement / buy value date | Trading operations, liquidity expectations | `VERIFIED_TEFAS_STRUCTURED` | Verified detail-page extraction and official-source cross-check | `profilData.fonGeriAlisValor`; persisted as raw fund-redemption/purchase-side valor metadata | No | KAP for supplementary disclosure | High | Observed semantics support `fonGeriAlisValor` as the investor purchase/buy settlement value date. Preserve the raw integer source value. |
| Sale settlement / sell value date | Trading operations, liquidity expectations | `VERIFIED_TEFAS_STRUCTURED` | Verified detail-page extraction and official-source cross-check | `profilData.fonSatisValor`; persisted as raw sale/redemption-side valor metadata | No | KAP for supplementary disclosure | High | Observed semantics support `fonSatisValor` as the investor sale/fund-redemption settlement value date. Preserve the raw integer source value. |
| Transaction start time | Order-window operations | `VERIFIED_TEFAS_STRUCTURED` | Verified TEFAS detail-page profile extraction | Detail-page profile metadata persisted as `transaction_start_time` | No | None | Medium | Nullable extraction and detail-snapshot persistence are implemented. |
| Transaction end time | Order-window operations | `VERIFIED_TEFAS_STRUCTURED` | Verified TEFAS detail-page profile extraction | Detail-page profile metadata persisted as `transaction_end_time` | No | None | Medium | Nullable extraction and detail-snapshot persistence are implemented. |
| Entrance commission | Cost disclosure | `VERIFIED_TEFAS_STRUCTURED` | Raw TEFAS detail-page field is extracted and persisted | `profilData.girisKomisyonu`; persisted as raw Decimal metadata | No | None | Medium | Extraction path is implemented, but no non-null live example was found in the bounded scan, so exact non-null business semantics remain intentionally unverified. |
| Exit commission | Cost disclosure | `VERIFIED_TEFAS_STRUCTURED` | Verified non-null TEFAS detail-page observation and KAP cross-check | `profilData.cikisKomisyonu`; persisted as raw Decimal metadata | No | KAP for supplementary disclosure | Medium | AZ1 provided a verified value of `3`, consistent with a 3% exit commission. Backend preserves the raw percentage-point magnitude as `Decimal("3")`, not `0.03`. |
| Interest-content information | Compliance/product screening | `VERIFIED_TEFAS_STRUCTURED` | Verified TEFAS detail-page profile extraction | Detail-page profile metadata persisted as `interest_content` | No | None | Medium | Nullable extraction and persistence are implemented; source wording is preserved rather than reinterpreted. |
| Management fee / fund management fee | Cost disclosure, net-return analysis | `VERIFIED_TEFAS_STRUCTURED` | Verified TEFAS management-fee endpoint for YAT and EMK | `fonYonetimBazliBilgiGetir`: `uygulananYu1Y` | No | None for YAT/EMK | High | YAT/EMK extraction, history persistence and bulk refresh/history sync are implemented. Scheduler/CLI/API integration and BYF/GYF/GSYF fee semantics remain intentionally deferred. Raw values are percentage points. |
| Benchmark | Relative-performance context, disclosures | `EXTERNAL_SOURCE_CANDIDATE` | `fonProfilDtyGetir` is verified to return TEFAS performance-comparison series, not the fund's legal benchmark | `fonProfilDtyGetir`: `fonKodu`, `fonUnvan`, `fonTuru`, `fonTurGetiri` | No | KAP | Medium | Keep TEFAS comparison series separate from official benchmark and threshold-value disclosures. Use a separately verified official source such as KAP if the legal benchmark becomes a product requirement. |
| Fund inception / start date | Lifecycle analytics, age filtering | `NEEDS_SOURCE_RESEARCH` | Legacy `getFplFonList.tarih` was observed historically but its meaning was never verified; the legacy endpoint is not a current production source | Legacy `getFplFonList`: `tarih` | No | KAP may be relevant | Medium | Do not interpret the legacy `tarih` value as fund inception/start date. Source this separately if required. |
| Currency | Valuation, display, reporting | `VERIFIED_TEFAS_STRUCTURED` | Verified currency lookup request | `v2` lookup: `dovizKod`, `dovizAd` | No | None | High | Verified auxiliary TEFAS currency metadata exists. |
| Fund total value | AUM, size, market-share denominator candidate | `VERIFIED_TEFAS_STRUCTURED` | Verified general-info endpoint; site metric concept `fundTotalValue` | `fonGnlBlgSiraliGetir`: `portfoyBuyukluk`, `tarih` | No | None | High | Verified raw TEFAS field exists. |
| Investor count | Participation breadth | `VERIFIED_TEFAS_STRUCTURED` | Verified general-info endpoint; site metric concept `investorCount` | `fonGnlBlgSiraliGetir`: `kisiSayisi`, `tarih` | No | None | High | Verified raw TEFAS field exists. |
| Shares outstanding | Ownership base size | `VERIFIED_TEFAS_STRUCTURED` | Verified general-info endpoint; site metric concept `fundShares` | `fonGnlBlgSiraliGetir`: `tedPaySayisi`, `tarih` | No | None | High | Verified raw TEFAS field exists. |
| Asset allocation | Portfolio exposure analysis | `VERIFIED_TEFAS_STRUCTURED` | Verified `dagilimSiraliGetirT` endpoint plus same-date TEFAS UI validation | `dagilimSiraliGetirT`: 54 observed allocation raw fields plus metadata; 43 raw fields have verified business-label mappings | No derivation required for verified mapped fields | None | High | 43 of 54 allocation fields have verified same-date raw/UI mappings. The remaining 11 fields (`bb`, `db`, `dot`, `eut`, `fkb`, `kh`, `kks`, `t`, `vm`, `yba`, `ymk`) remained null/zero across 12,476 tested raw rows and are preserved as unobserved/unused raw fields without guessed labels. |
| Historical price | Performance and risk analytics base series | `VERIFIED_TEFAS_STRUCTURED` | Verified historical-price endpoint plus BYF cross-endpoint validation | `fonFiyatBilgiGetir`: `fonKodu`, `fonUnvan`, `kategoriDerece`, `kategoriFonSay`, `tarih`, `fiyat`; general-info `borsaBultenFiyat` | No | None | High | For the verified 2026-04-24 BYF cross-section, historical `fiyat` matched `borsaBultenFiyat` in 30/30 cases, while general-info `fiyat` represented the distinct calculated per-share fund value / NAV behavior. Keep endpoint-specific price semantics separate. |
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

The remaining questions are intentionally deferred and do not block the current
TEFAS backend MVP:

- What is the exact non-null business meaning of `girisKomisyonu`? Extraction
  and persistence exist, but no non-null live example was found in the bounded
  scan.
- What current authoritative source should be used for founder / management
  company, operator, and fund lifecycle status if those fields become product
  requirements? Legacy `getFplFonList` observations must not be treated as a
  current production contract.
- What is the authoritative fund inception/start-date source? The legacy
  `getFplFonList.tarih` field must not be interpreted as inception date.
- What are the verified management-fee semantics for `BYF`, `GYF`, and `GSYF`?
  YAT/EMK support is already implemented.
- If a legally defined official benchmark or threshold value becomes required,
  which KAP disclosure path should be adopted as the backend source?
- What TEFAS grouping should define the denominator for a custom derived
  fund-market-share metric?

## Summary view

Covered by verified TEFAS structured extraction and/or backend persistence:

- Main fund kind (`YAT`, `EMK`, `BYF`, `GYF`, `GSYF`).
- Business-level fund type from `fonProfilDtyGetir.fonTuru`.
- ISIN code.
- Official TEFAS fund risk value.
- Platform status.
- Transaction start and end times.
- Purchase/buy and sale/redemption settlement-value metadata.
- Raw entrance and exit commission fields.
- Interest-content information.
- Currency.
- Fund total value / AUM proxy.
- Investor count.
- Shares outstanding.
- Historical price.
- BYF NAV/per-share-value and exchange-bulletin price fields as separate
  endpoint-specific concepts.
- Asset allocation (43 verified mappings; 11 unobserved raw fields preserved).
- 1-year category ranking.
- YAT/EMK management-fee extraction and history persistence.

Available from verified TEFAS derivation:

- Historical returns.
- Estimated net fund flow / inflow-outflow.
- Other implemented short-term evolution metrics based on persisted daily data.

Resolved production decisions:

- TEFAS internal `fonTipiGetir` codes are provider-internal metadata and are not
  persisted as user-facing classifications.
- `fonProfilDtyGetir` comparison rows are performance-comparison series and must
  not be equated with a fund's legally defined benchmark.
- For the verified `2026-04-24` BYF cross-section,
  `fonFiyatBilgiGetir.fiyat` matched `borsaBultenFiyat` in 30/30 cases, while
  general-info `fiyat` behaved as the distinct calculated per-share fund
  value / NAV.
- `fonSatisValor` and `fonGeriAlisValor` have verified settlement-side
  interpretations from live TEFAS observations and official-source
  cross-checking; raw integer source values remain preserved.
- Legacy `getFplFonList.tarih` is not used as an inception-date source.

Still deferred / requiring a separately verified source or semantics:

- Exact non-null `girisKomisyonu` semantics.
- Current founder / management company, operator, and lifecycle-directory
  metadata.
- Fund inception / start date.
- Official legal benchmark / threshold disclosure if required.
- BYF/GYF/GSYF management-fee semantics.
- Management-fee scheduler / daily-sync / CLI / API integration.
- Fund-market-share denominator grouping.
- The 11 unobserved portfolio-allocation raw fields.
