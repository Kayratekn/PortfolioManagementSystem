# TEFAS Integration Decisions

## Goal

The goal of this integration is to collect public fund data directly from
TEFAS without using `tefas-crawler` or `pytefas` as runtime dependencies.

The source code of these projects was examined only to understand:

- TEFAS endpoint URLs
- HTTP methods
- Request headers
- Request body structures
- Response structures
- Rate-limit and date-range approaches

Our application will communicate directly with TEFAS through its own
`CustomTefasClient`.

## Selected general information endpoint

The selected endpoint for general fund information is:

```text
POST https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir
```

This endpoint returned the following raw fields:

- `fonKodu`
- `fonUnvan`
- `tarih`
- `fiyat`
- `tedPaySayisi`
- `kisiSayisi`
- `portfoyBuyukluk`
- `borsaBultenFiyat`
- `rn`

The usable fields include:

- Fund code
- Fund name
- Data date
- Price
- Outstanding share count
- Investor count
- Portfolio size
- Exchange bulletin price

The TEFAS internal `rn` field will not be stored.

## Daily bulk collection decision

The preferred daily collection structure is:

```text
1 request = 1 fund type + 1 day + multiple funds
```

The live test used:

```text
Fund type: YAT
Fund code: null
Start date: 20260424
End date: 20260424
```

The result was:

- HTTP request count: 1
- HTTP status: 200
- Duration: 1.48 seconds
- Record count: 1995
- Unique fund count: 1995
- Unique date count: 1
- Returned date: 2026-04-24

This confirms that general daily information does not need to be requested
separately for every fund.

The system should request data by fund type instead of sending one request for
every fund code.

Possible fund types observed in the reference projects are:

- `YAT`
- `EMK`
- `BYF`
- `GYF`
- `GSYF`

The fund types required by the project must later be confirmed with the data
team.

## Single fund and single day result

The live test used:

```text
Fund type: YAT
Fund code: AAL
Start date: 20260424
End date: 20260424
```

The result was:

- HTTP request count: 1
- HTTP status: 200
- Duration: 0.28 seconds
- Record count: 1
- Returned fund code: AAL
- Returned date: 2026-04-24

The returned record included:

```json
{
  "fonKodu": "AAL",
  "fonUnvan": "ATA PORTFÖY PARA PİYASASI (TL) FONU",
  "tarih": "2026-04-24",
  "fiyat": 3.163587,
  "tedPaySayisi": 960084201,
  "kisiSayisi": 4845,
  "portfoyBuyukluk": 3037309510.91,
  "borsaBultenFiyat": null
}
```

This confirms that the `fonKodu` request filter works when the selected fund
exists in the requested date's dataset.

An earlier test with fund code `AAK` returned no records because `AAK` was not
present in the `YAT` dataset for the selected date.

## Single fund and date range result

The live test used:

```text
Fund type: YAT
Fund code: AAL
Start date: 20260401
End date: 20260424
```

The result was:

- HTTP request count: 1
- HTTP status: 200
- Duration: 0.30 seconds
- Record count: 17
- Unique fund count: 1
- Unique date count: 17
- First returned date: 2026-04-01
- Last returned date: 2026-04-24

All returned records belonged to fund code `AAL`.

Only dates with available fund data were returned. Weekends and dates without
available data were not included.

This confirms that one request can return a selected fund's information for a
date range.

## Date-range decision

The `pytefas` reference implementation uses a conservative maximum range of
28 days per request.

Our integration should also use a maximum of 28 days for one TEFAS request
until longer ranges are tested directly.

Longer date ranges should later be divided into consecutive 28-day chunks.

Example:

```text
Requested range: 2026-01-01 to 2026-03-31

Chunk 1: 2026-01-01 to 2026-01-28
Chunk 2: 2026-01-29 to 2026-02-25
Chunk 3: 2026-02-26 to 2026-03-25
Chunk 4: 2026-03-26 to 2026-03-31
```

Automatic date-range chunking is not implemented in the current spike.

## Missing-data behavior

TEFAS may return HTTP 200 even when no data is available.

The following response was observed:

```json
{
  "errorCode": null,
  "errorMessage": "Index 0 out of bounds for length 0",
  "resultList": null,
  "toplamSayi": null,
  "toplamSayfa": null
}
```

This occurred for the date `2026-07-30`.

The current `TefasService` interprets an error message containing
`out of bounds` as an empty result instead of a fatal application error.

Recent-date publication timing and data availability still require further
investigation.

## Portfolio breakdown endpoint

Portfolio asset-allocation information requires a separate endpoint:

```text
POST https://www.tefas.gov.tr/api/funds/dagilimSiraliGetirT
```

This endpoint is intended to return portfolio allocation information.

Possible normalized fields may include:

- `stock_pct`
- `government_bond_pct`
- `private_bond_pct`
- `repo_pct`
- `gold_pct`
- `foreign_asset_pct`
- `cash_pct`

The portfolio breakdown endpoint has not yet been live-tested in this spike.

Its raw response fields must be inspected before final normalization rules are
implemented.

No allocation field should be guessed or fabricated before the live response
is verified.

## Field normalization decision

The general information response is converted as follows:

| TEFAS field | Normalized field |
|---|---|
| `fonKodu` | `fund_code` |
| `fonUnvan` | `fund_name` |
| Request parameter `fonTipi` | `fund_kind` |
| `tarih` | `data_date` |
| `fiyat` | `price` |
| `tedPaySayisi` | `shares_outstanding` |
| `kisiSayisi` | `investor_count` |
| `portfoyBuyukluk` | `portfolio_size` |
| `borsaBultenFiyat` | `exchange_bulletin_price` |
| `rn` | Not stored |

The normalized example is:

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

Normalization rules:

- Fund codes must be trimmed and converted to uppercase.
- Fund kinds must be stored in uppercase.
- Fund names must have leading and trailing whitespace removed.
- Dates must use ISO format: `YYYY-MM-DD`.
- Financial values must later use `Decimal` when stored or calculated.
- Nullable values must remain null.
- Missing values must not automatically be replaced with zero.
- TEFAS internal row numbers must not be stored.
- General information and portfolio breakdown data must remain separate until
  they are safely matched by fund code and date.

## Application structure

The current structure is:

```text
CustomTefasClient
    ↓
Direct HTTP communication with TEFAS

TefasService
    ↓
TEFAS application-error handling
Response extraction
Field normalization

Repository and PostgreSQL
    ↓
Not implemented in this spike
```

Current implementation files:

```text
src/integrations/__init__.py
src/integrations/tefas_client.py
src/services/tefas_service.py
```

The client is responsible for:

- Building TEFAS request bodies
- Sending direct HTTP POST requests
- Applying request headers
- Handling HTTP errors
- Parsing JSON responses

The service is responsible for:

- Reading `resultList`
- Handling TEFAS application errors
- Returning empty lists for known no-data responses
- Converting raw TEFAS fields into normalized fields

The current client and service do not write data to the database.

## Database recommendation

Database integration is outside the current research spike.

When it is implemented, the daily fund-data table should use a unique business
key similar to:

```text
fund_code + data_date
```

Repeated imports should use an upsert strategy.

This prevents the same fund and date from producing duplicate records.

Possible future flow:

```text
TEFAS
    ↓
CustomTefasClient
    ↓
TefasService
    ↓
Repository
    ↓
PostgreSQL upsert
```

## Scheduling recommendation

Daily automatic collection is not implemented in this spike.

A future scheduler should:

1. Determine the latest expected TEFAS data date.
2. Request each required fund type.
3. Use one bulk request per fund type and day.
4. Validate the returned records.
5. Upsert records using `fund_code + data_date`.
6. Record request duration and record count.
7. Retry temporary failures with controlled delays.
8. Avoid unnecessary repeated requests.


## Created research files

Research documents:

```text
docs/tefas_endpoint_notes.md
docs/tefas_field_mapping.md
docs/tefas_decisions.md
```

Verified response samples:

```text
docs/sample_tefas_aal_single_day.json
docs/sample_tefas_aal_single_day.csv
docs/sample_tefas_aal_date_range.json
docs/sample_tefas_all_yat_known_date_preview.json
```

The bulk preview contains 10 example records.

The live request returned 1995 records in total, but the complete raw response
was not committed because it was unnecessarily large.

Probe scripts:

```text
scripts/tefas_probe_single_fund.py
scripts/tefas_probe_single_fund_range.py
scripts/tefas_sample_to_csv.py
```


## Current verification status

Completed:

- TEFAS endpoint research
- HTTP method research
- Request-header research
- Request-body research
- Response-structure research
- Single fund / single day live test
- Single fund / date range live test
- Fund type / single day bulk live test
- Raw JSON samples
- Normalized CSV sample
- Field mapping document
- `CustomTefasClient` skeleton
- `TefasService` skeleton
- General information normalization
- Known no-data response handling

Test results:

```text
TEFAS service unit tests: 3 passed
Full project test suite: 28 passed
```

Existing authentication and Portfolio functionality remained operational.

## Remaining work

The following work is not completed yet:

- Live-test the portfolio breakdown endpoint
- Inspect portfolio breakdown raw fields
- Finalize allocation-field mappings
- Test the required fund types separately
- Confirm recent-data publication timing
- Add automatic 28-day range chunking
- Add controlled retry and rate-limit behavior
- Add database models
- Add repository and upsert logic
- Add daily scheduling
- Add logging and collection-run monitoring

These remaining items should be implemented as separate, small features after
the current research spike is reviewed.