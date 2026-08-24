# TEFAS Fund Discovery

## Verified discovery observations

This document contains both:

- Verified live data-probe observations.
- Later browser/site discovery observations.

These observations do not prove that TEFAS has no additional fields,
endpoints, or response shapes.

## Live data probe for 2026-04-24

## Verified raw endpoint observations

### `POST /api/funds/fonGnlBlgSiraliGetir`

Observed via `fetch_general_info`.

Verified fund kinds returning data:

- `YAT`
- `EMK`
- `BYF`
- `GYF`
- `GSYF`

Verified row counts:

| Fund kind | Rows |
|---|---:|
| `YAT` | 1995 |
| `EMK` | 392 |
| `BYF` | 30 |
| `GYF` | 239 |
| `GSYF` | 498 |

Observed raw fields:

- `fonKodu`
- `fonUnvan`
- `tarih`
- `fiyat`
- `tedPaySayisi`
- `kisiSayisi`
- `portfoyBuyukluk`
- `borsaBultenFiyat`
- `rn`

### `POST /api/funds/dagilimSiraliGetirT`

Observed via `fetch_portfolio_breakdown`.

Verified fund kinds returning data:

- `YAT`
- `EMK`
- `BYF`
- `GYF`
- `GSYF`

Verified row counts:

| Fund kind | Rows |
|---|---:|
| `YAT` | 1985 |
| `EMK` | 392 |
| `BYF` | 29 |
| `GYF` | 233 |
| `GSYF` | 491 |

Observed raw fields:

- `bb`
- `bilFiyat`
- `bpp`
- `btaa`
- `btas`
- `byf`
- `d`
- `db`
- `dot`
- `dt`
- `eut`
- `fb`
- `fkb`
- `fonKodu`
- `fonUnvan`
- `gas`
- `gsykb`
- `gsyy`
- `gykb`
- `gyy`
- `hb`
- `hs`
- `kba`
- `kh`
- `khau`
- `khd`
- `khtl`
- `kibd`
- `kks`
- `kksd`
- `kkstl`
- `kksyd`
- `km`
- `kmbyf`
- `kmkba`
- `kmkks`
- `oksyd`
- `osdb`
- `osks`
- `ost`
- `r`
- `t`
- `tarih`
- `tpp`
- `tr`
- `vdm`
- `vint`
- `vm`
- `vmau`
- `vmd`
- `vmtl`
- `yba`
- `ybkb`
- `ybosb`
- `ybyf`
- `yhs`
- `ymk`
- `yyf`

These 58 names are documented only as verified raw fields. No meanings are
assigned here for abbreviated portfolio fields.

### `POST /api/funds/fonDetayGetir`

Observed example payload:

```json
{
  "fonTipi": "BYF",
  "dil": "TR"
}
```

Observed raw result fields:

- `fonTipi`
- `fonTurKod`
- `fonTurAciklama`

Observed purpose:

- Fund subtype/category metadata.

### `POST /api/funds/fonUnvanGetir`

Observed example payload:

```json
{
  "dil": "TR",
  "tur": "BYF"
}
```

Observed raw result field:

- `tanim`

Observed purpose:

- Fund classification/title metadata.

### `POST /api/funds/fonTipiGetir`

Observed example payload:

```json
{
  "fonKodu": "BLH"
}
```

Observed response:

```json
{
  "fonTipi": "N"
}
```

Observed classification behavior:

- A bounded live scan of 20 active funds from each TEFAS fund kind produced a
  consistent `fonTipiGetir` mapping with no errors:
  - `YAT -> F` (20/20)
  - `EMK -> M` (20/20)
  - `BYF -> N` (20/20)
  - `GYF -> 1` (20/20)
  - `GSYF -> 0` (20/20)
- These values are treated as TEFAS provider-internal type codes, not as
  user-facing business category names.
- They are not persisted as a separate business classification in the backend.
- Business-level fund-type history continues to use
  `fonProfilDtyGetir.fonTuru`.
- `fonDetayGetir` did not behave as a universal subtype-master endpoint in the
  tested calls: `EMK` and `BYF` returned structured subtype rows, while `YAT`,
  `GYF`, and `GSYF` returned no rows. Do not assume identical availability
  across every fund kind.

### `POST /api/funds/fonFiyatBilgiGetir`

Observed example payload for `BLH`:

```json
{
  "fonKodu": "BLH",
  "dil": "TR",
  "periyod": 12
}
```

Observed raw result fields:

- `fonKodu`
- `fonUnvan`
- `kategoriDerece`
- `kategoriFonSay`
- `tarih`
- `fiyat`

Observed behavior:

- Returns historical daily price-series data for the selected period.

Verified `BYF` price behavior on `2026-04-24`:

- The original `BLH` observation showed:
  - General-info `fiyat` = `49.222014`
  - General-info `borsaBultenFiyat` = `49.24`
  - `fonFiyatBilgiGetir` `fiyat` = `49.24`
- The same-date cross-section was then checked across all 30 available `BYF`
  rows:
  - `fonFiyatBilgiGetir.fiyat` matched `borsaBultenFiyat` in 30/30 cases.
  - It differed from general-info `fiyat` in 30/30 cases.
  - No tested row was missing `borsaBultenFiyat`.
- A separate arithmetic check across those same 30 `BYF` rows found that
  general-info `fiyat` matched `portfoyBuyukluk / tedPaySayisi` in 30/30
  cases within the chosen numeric tolerance.
- This is consistent with the official BYF pricing model in which calculated
  per-share fund value / NAV and exchange-market transaction price are distinct
  values.

Production interpretation:

- For observed `BYF` behavior, general-info `fiyat` is treated as the calculated
  per-share fund value / NAV.
- `borsaBultenFiyat` is treated as the exchange-market / bulletin price.
- `fonFiyatBilgiGetir.fiyat` matched the exchange bulletin price in the verified
  `2026-04-24` cross-section.
- Endpoint-specific price fields must therefore remain separate; a generic
  `fiyat` field name must not be assumed to carry identical semantics across
  TEFAS endpoints.

`kategoriDerece` and `kategoriFonSay` are treated as the TEFAS-displayed
one-year category rank and category fund count respectively. Null or zero source
values must still be preserved conservatively rather than interpreted as valid
ranks.

### `POST /api/funds/fonProfilDtyGetir`

Observed example payload:

```json
{
  "dil": "TR",
  "fonKodu": "BLH",
  "periyod": "12"
}
```

Observed raw result fields:

- `fonKodu`
- `fonUnvan`
- `fonTuru`
- `fonTurGetiri`

Observed behavior:

- Returns period-return / comparison data.
- Observed result includes the selected fund plus comparison or benchmark
  series such as `ALTIN`, `BIST100`, `BIST30`, `EUR`, `USD`, `TUFE`, and
  `MEVDUAT FAIZI`.

### `POST /api/funds/getFplFonList`

Observed example payload:

```json
{}
```

Observed response collection key:

- `data`

Observed raw fields:

- `fonKod`
- `unvan`
- `kurucuKod`
- `kurucuAd`
- `oprKod`
- `oprAd`
- `durum`
- `tarih`

Observed purpose:

- Broad fund master/directory data including fund, founder/management company,
  operator, and status metadata.

This document does not assign a confirmed semantic meaning to the `tarih`
field from this endpoint.

### Currency lookup request (`v2`)

Observed example payload:

```json
{
  "fonKodu": "",
  "dil": "TR"
}
```

Observed raw fields:

- `dovizKod`
- `dovizAd`

Observed values included:

- `TL` / `TÜRK LIRASI`
- `USD` / `AMERIKAN DOLARI`
- `EUR` / `EURO`

Observed purpose:

- Auxiliary currency metadata.

## Site-observed metric labels and descriptions

The TEFAS site resources expose the following metric keys or labels. These are
site-observed metric concepts, not necessarily raw fields returned by a single
API endpoint:

- `fundPrice`
- `dailyReturn`
- `fundShares`
- `fundTotalValue`
- `fundCategory`
- `fundCategoryDegree`
- `investorCount`
- `marketShare`
- `oneMonthReturn`
- `threeMonthReturn`
- `sixMonthReturn`
- `yearToDateReturn`
- `oneYearReturn`
- `threeYearReturn`
- `fiveYearReturn`
- `assetType`
- `percentage`

Observed TEFAS descriptions:

- `dailyReturn` is calculated from the daily percentage change in fund prices.
- Period return values use the percentage change between period-start and
  period-end reported prices.
- `marketShare` is described as: Fund Total Value / Total Fund Total Value of
  funds in the relevant type.
- `fundCategoryDegree` is described as the one-year return ranking among funds
  in the fund's own type.
- `investorCount` is the number of people investing in the fund.
- Asset allocation represents the latest data reported to Takasbank.

## Unresolved meanings

The following items remain unresolved or intentionally deferred and should not
receive guessed production semantics:

- The 11 portfolio-breakdown raw fields `bb`, `db`, `dot`, `eut`, `fkb`, `kh`,
  `kks`, `t`, `vm`, `yba`, and `ymk`. They remained null/zero across the
  existing broad raw-data scan and therefore keep their raw names without
  guessed business labels.
- The exact business meaning of the legacy `getFplFonList.tarih` field remains
  unresolved. The legacy endpoint is not used as a current production source,
  and this field must not be interpreted as fund inception/start date.
- TEFAS internal classification codes such as `F`, `M`, `N`, `1`, and `0` are
  verified as stable observed fund-kind mappings in the bounded scan, but their
  provider-internal naming semantics are not needed for the business domain.
- Fund-market-share denominator grouping still requires an explicit definition
  of the relevant TEFAS grouping before a custom derived production metric is
  used.

## Production-use and access considerations

Observed TEFAS FAQ and site-operation notes:

- TEFAS states that it does not provide an official API sharing/service for
  platform data.
- Fund data is not updated in real time; updates occur periodically during the
  day.
- TEFAS points users to KAP for settlement/value-date information for all
  funds.

These observations are relevant to production access and operational planning,
not proof that these discovered endpoints should be implemented in production.

## Current scope limit

Discovery is not complete yet.

The current document records verified raw endpoint observations, validated
business semantics, intentionally deferred gaps, and operational/access notes.
Production use must follow the conservative backend decisions documented here
and in `PROJECT_STATUS.md`; an observed TEFAS endpoint is not automatically a
stable production contract.

## Future discovery only if required

The TEFAS backend MVP discovery phase is complete. Remaining discovery is
intentionally deferred unless a concrete product requirement makes it necessary:

- Do not assign guessed meanings to the 11 portfolio-breakdown fields that
  remained unobserved/null-zero in the existing broad scan.
- Do not create a separate business-domain model for provider-internal
  `fonTipiGetir` codes; the observed `YAT -> F`, `EMK -> M`, `BYF -> N`,
  `GYF -> 1`, and `GSYF -> 0` mapping is sufficient for current provider-level
  understanding.
- Re-verify current authoritative sources for legacy directory metadata or fund
  inception date if those fields become product requirements.
- Continue preserving endpoint-specific semantics for similarly named TEFAS
  fields rather than assuming equivalence from field names alone.
