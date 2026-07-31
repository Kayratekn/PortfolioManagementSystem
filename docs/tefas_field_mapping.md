# TEFAS Field Mapping

## Purpose

This document defines how raw TEFAS response fields are converted into the
normalized field names used by the Portfolio Management System.

## General information mapping

| TEFAS field | Normalized field | Type | Required | Notes |
|---|---|---|---|---|
| `fonKodu` | `fund_code` | string | Yes | Unique TEFAS fund code |
| `fonUnvan` | `fund_name` | string | Yes | Full fund name |
| Request parameter `fonTipi` | `fund_kind` | string | Yes | Examples: `YAT`, `EMK`, `BYF`, `GYF`, `GSYF` |
| `tarih` | `data_date` | date | Yes | Convert to ISO date format `YYYY-MM-DD` |
| `fiyat` | `price` | decimal | Yes | Fund unit price |
| `tedPaySayisi` | `shares_outstanding` | decimal | No | Outstanding participation-share count |
| `kisiSayisi` | `investor_count` | integer | No | Number of investors |
| `portfoyBuyukluk` | `portfolio_size` | decimal | No | Total fund portfolio size |
| `borsaBultenFiyat` | `exchange_bulletin_price` | decimal or null | No | May be null |
| `rn` | Not stored | integer | No | TEFAS response row number; internal field |

## Portfolio breakdown mapping

Portfolio asset-allocation information is not returned by the general
information endpoint.

It must be requested separately from:

```text
POST /api/funds/dagilimSiraliGetirT
```

The allocation fields will later be converted into normalized percentage
fields such as:

- `stock_pct`
- `government_bond_pct`
- `private_bond_pct`
- `repo_pct`
- `gold_pct`
- `foreign_asset_pct`
- `cash_pct`

The exact raw-field mapping must be completed after the portfolio-breakdown
endpoint is tested.

## Example raw TEFAS record

```json
{
  "fonKodu": "AAL",
  "fonUnvan": "ATA PORTFÖY PARA PİYASASI (TL) FONU",
  "tarih": "2026-04-24",
  "fiyat": 3.163587,
  "tedPaySayisi": 960084201,
  "kisiSayisi": 4845,
  "portfoyBuyukluk": 3037309510.91,
  "borsaBultenFiyat": null,
  "rn": 1
}
```

## Example normalized output

```json
{
  "fund_code": "AAL",
  "fund_name": "ATA PORTFÖY PARA PİYASASI (TL) FONU",
  "fund_kind": "YAT",
  "data_date": "2026-04-24",
  "price": 3.163587,
  "shares_outstanding": 960084201,
  "investor_count": 4845,
  "portfolio_size": 3037309510.91,
  "exchange_bulletin_price": null
}
```

## Normalization rules

- Trim leading and trailing whitespace from fund codes and names.
- Convert `fund_code` and `fund_kind` to uppercase.
- Parse `data_date` as a date, not as free text.
- Use `Decimal` for financial values when data is stored or calculated.
- Preserve nullable fields as null; do not replace missing values with zero.
- Do not store the TEFAS internal `rn` field.
- Do not fabricate fields that are absent from the TEFAS response.
- General information and portfolio breakdown must remain separate until both
  responses are successfully matched by fund code and date.