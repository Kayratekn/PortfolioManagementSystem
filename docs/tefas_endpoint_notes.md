# TEFAS Endpoint Research Notes

## Research sources

- tefas-crawler
- pytefas

## Fund price endpoint

Endpoint:

```text
https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir
```

Method:

```text
POST
```

Request body:

```json
{
  "fonKodu": "FUND_CODE",
  "dil": "TR",
  "periyod": 1
}
```

Observed period values:

- 1 month
- 3 months
- 6 months
- 12 months
- 36 months
- 60 months

Headers:

```text
User-Agent: Mozilla/5.0 ...
Content-Type: application/json
Accept: application/json, text/plain, */*
```

Timeout:

```text
30 seconds
```

Response data path:

```text
resultList
```

Source-code observations:

- The endpoint accepts one fund code.
- It does not accept exact start and end dates.
- The client requests a predefined month period.
- Exact dates are filtered locally after the response is received.
- Live behavior still needs to be tested.

## Fund list endpoint

Endpoint:

```text
https://www.tefas.gov.tr/api/funds/fonGetiriBazliBilgiGetir
```

Method:

```text
POST
```

Request body:

```json
{
  "dil": "TR",
  "fonTipi": "YAT",
  "kurucuKodu": null,
  "sfonTurKod": null,
  "fonTurAciklama": null,
  "islem": 1,
  "fonTurKod": null,
  "fonGrubu": null,
  "donemGetiri1a": "1",
  "donemGetiri3a": "1",
  "donemGetiri6a": "1",
  "donemGetiri1y": "1",
  "donemGetiriyb": "1",
  "donemGetiri3y": "1",
  "donemGetiri5y": "1",
  "basTarih": null,
  "bitTarih": null,
  "calismaTipi": 2,
  "getiriOrani": "1"
}
```

Headers:

```text
User-Agent: Mozilla/5.0 ...
Content-Type: application/json
Accept: application/json, text/plain, */*
```

Response data path:

```text
resultList
```

Source-code observations:

- One request appears to return multiple funds.
- The `fonTipi` field selects the fund type.
- Possible examples include `YAT`, `EMK` and `BYF`.
- tefas-crawler extracts the fund codes from this response.
- It then sends a separate price request for every fund code.
- Live behavior and record counts still need to be tested.

## pytefas general information endpoint

Endpoint:

```text
https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir
```

Method:

```text
POST
```

Request body:

```json
{
  "fonTipi": "YAT",
  "fonKodu": null,
  "aramaMetni": null,
  "fonTurKod": null,
  "fonGrubu": null,
  "sfonTurKod": null,
  "fonTurAciklama": null,
  "kurucuKod": null,
  "basTarih": "20260730",
  "bitTarih": "20260730",
  "basSira": 1,
  "bitSira": 100000,
  "dil": "TR",
  "sFonTurKod": "",
  "fonKod": "",
  "fonGrup": "",
  "fonUnvanTip": ""
}
```

Headers:

```text
Accept: */*
Content-Type: application/json
Origin: https://www.tefas.gov.tr
Referer: https://www.tefas.gov.tr/tr/fon-verileri
User-Agent: Mozilla/5.0 ...
```

Response data path:

```text
resultList
```

Source-code observations:

- Exact start and end dates are supported.
- Date format is `YYYYMMDD`.
- When `fonKodu` is null, the request attempts to return all funds for the selected fund type.
- When `fonKodu` contains a fund code, the request filters to that fund.
- `basSira: 1` and `bitSira: 100000` appear to request a large result range.
- pytefas limits each request to 28 days and splits longer ranges into multiple requests.
- Live behavior and actual record count still need to be tested.

## pytefas portfolio breakdown endpoint

Endpoint:

```text
https://www.tefas.gov.tr/api/funds/dagilimSiraliGetirT
```

Method:

```text
POST
```

Request body:

- Uses the same body structure as the general information endpoint.
- This endpoint returns portfolio asset-allocation information.

Response data path:

```text
resultList
```

Source-code observation:

- General fund information and portfolio breakdown require separate requests.
- Live behavior and response fields still need to be tested.

## Test results

### Single fund / single day

Request:

- Endpoint: `POST /api/funds/fonGnlBlgSiraliGetir`
- Fund type: `YAT`
- Fund code: `AAL`
- Start date: `20260424`
- End date: `20260424`
- HTTP request count: `1`

Status:

- HTTP 200
- No TEFAS application error

Duration:

- 0.28 seconds

Record count:

- 1 record
- Fund code: `AAL`
- Returned date: `2026-04-24`

Result:

- Successful.
- The `fonKodu` request filter works when the selected fund exists on the requested date.
- The response contained price, shares, investor count and portfolio size data.
- `borsaBultenFiyat` was null for this record.
- The earlier `AAK` test returned no records because `AAK` was not present in the selected date's YAT dataset.

### Single fund / date range

Request:

- Endpoint: `POST /api/funds/fonGnlBlgSiraliGetir`
- Fund type: `YAT`
- Fund code: `AAL`
- Start date: `20260401`
- End date: `20260424`
- HTTP request count: `1`

Status:

- HTTP 200
- No TEFAS application error

Duration:

- 0.30 seconds

Record count:

- 17 records
- 17 unique dates
- 1 unique fund code
- Fund code: `AAL`
- First returned date: `2026-04-01`
- Last returned date: `2026-04-24`

Result:

- Successful.
- One request returned the selected fund's data for the requested date range.
- All returned records belonged to fund code `AAL`.
- Only dates with available fund data were returned.
- Weekends and dates without available data were not included in the response.

### Fund type / single day

Request:

- Endpoint: `POST /api/funds/fonGnlBlgSiraliGetir`
- Fund type: `YAT`
- Fund code: `null`
- Start date: `20260424`
- End date: `20260424`
- HTTP request count: `1`

Status:

- HTTP 200
- No TEFAS application error

Duration:

- 1.48 seconds

Record count:

- 1995 records
- 1995 unique fund codes
- 1 unique date
- Returned date: `2026-04-24`

Result:

- Successful.
- One request returned multiple funds for a single day.
- This confirms that daily general fund information does not need to be requested separately for every fund.
- The same request made for `20260730` returned no records and the TEFAS message `Index 0 out of bounds for length 0`.
- Recent-day data availability or publication timing requires further investigation.

## Response fields

-

## Missing fields

-

## Rate-limit observations

-

## Notes for the next developer

-