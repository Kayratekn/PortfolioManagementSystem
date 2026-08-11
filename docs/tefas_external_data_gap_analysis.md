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
| Fund risk value / risk score | Risk disclosure and filtering | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Manually observed on TEFAS site fund-profile concepts | None verified yet | No | None yet | High | Site-visible, but no verified raw endpoint/value source yet. |
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
| Asset allocation | Portfolio exposure analysis | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Verified structured endpoint exists, and site describes allocation as latest Takasbank-reported data | `dagilimSiraliGetirT`: abbreviated fields such as `bb`, `bpp`, `gsykb`, `vdm`, `tarih` | Not safely yet | None yet | High | Structured path exists, but abbreviated raw fields are not decoded; not production-ready yet. |
| Historical price | Performance and risk analytics base series | `VERIFIED_TEFAS_STRUCTURED` | Verified historical-price endpoint | `fonFiyatBilgiGetir`: `fonKodu`, `fonUnvan`, `kategoriDerece`, `kategoriFonSay`, `tarih`, `fiyat` | No | None | High | For `BYF`, `fiyat` semantics differ from `fonGnlBlgSiraliGetir.fiyat` in the verified `BLH` observation. |
| Historical returns | Performance metrics over time | `DERIVABLE_FROM_TEFAS` | Metric matrix confirms derivation from verified historical prices; site exposes return concepts | Primarily `fonFiyatBilgiGetir`: `fiyat`, `tarih` | Yes | None | High | Daily, 5-day, 1-month, 3-month, 6-month, YTD, 1-year and longer-window returns can be derived conservatively from price history. |
| Category ranking | Relative ranking within category | `TEFAS_SITE_VISIBLE_NEEDS_EXTRACTION_VALIDATION` | Site metric concept `fundCategoryDegree`; verified historical-price endpoint includes unresolved ranking-style fields | `fonFiyatBilgiGetir`: `kategoriDerece`, `kategoriFonSay` | Not safely yet | None yet | Medium | Ranking semantics remain unresolved; not production-ready. |

## Recommended external-source investigation order

1. TEFAS structured/site source validation.
2. KAP or another primary official source.
3. FVT only for important remaining gaps.

## Likely MVP external-data needs

Current evidence does not prove that an external source is necessary for the
core MVP metrics already supported by verified TEFAS data, such as fund total
value, investor count, shares outstanding, historical price, historical
returns, founder/management company, operator, category/subtype metadata, and
active/inactive status.

The most likely early external-data candidate is KAP for settlement/value-date
information if TEFAS site extraction cannot be validated as a stable structured
source.

No current evidence justifies recommending FVT for the MVP yet.

## Questions still requiring discovery

- Is there a stable structured TEFAS extraction path for site-visible fields such as ISIN, risk value, platform status, transaction times, commissions, and interest-content information?
- What do the abbreviated `dagilimSiraliGetirT` asset-allocation fields mean?
- Do `kategoriDerece` and `kategoriFonSay` actually represent category ranking, and if so, what is the exact denominator/grouping logic?
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

Available from verified TEFAS derivation:

- Historical returns.

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
- Asset allocation semantics.
- Category ranking semantics.

Still needing source research:

- Management fee / fund management fee.
- Official benchmark.
- Fund inception / start date.
