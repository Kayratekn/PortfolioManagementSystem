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

Observed note:

- `N` appears to be a separate internal classification value.
- Its meaning has not yet been resolved.
- This document does not claim that `N` means `BYF`.

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

Important `BYF` observation for `BLH` on `2026-04-24`:

- General-info `fiyat` = `49.222014`
- General-info `borsaBultenFiyat` = `49.24`
- `fonFiyatBilgiGetir` `fiyat` = `49.24`

Therefore, a field named `fiyat` must not be assumed to have identical
semantics across every TEFAS endpoint, especially for `BYF`.

This document does not assign a confirmed meaning to `kategoriDerece` or
`kategoriFonSay`.

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

The following items remain unresolved and should not be treated as confirmed
production semantics yet:

- Abbreviated portfolio-breakdown fields such as `bb`, `bpp`, `gsykb`, `vdm`,
  and similar short keys.
- The meaning of `fonTipi = N` returned by `fonTipiGetir`.
- The exact semantics of `kategoriDerece` and `kategoriFonSay`.
- Whether fields with the same name across endpoints, especially `fiyat`, carry
  identical business meaning.
- The exact meaning of the `tarih` field returned by `getFplFonList`.

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

The current document records verified raw endpoint observations, site metric
labels/descriptions, unresolved meanings, and operational/access notes. It does
not recommend production implementation of the newly observed endpoints yet.

## Next discovery step

Remaining discovery work:

- Inspect additional TEFAS endpoints and related site resources.
- Resolve abbreviated portfolio-breakdown field meanings from verified
  evidence.
- Determine the business meaning of `fonTipi = N`.
- Compare similarly named fields across endpoints before assuming semantic
  equivalence.
