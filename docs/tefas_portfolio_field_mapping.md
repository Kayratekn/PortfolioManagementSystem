# TEFAS Portfolio Field Mapping

## Raw response structure

`dagilimSiraliGetirT` exposes 58 observed raw fields.

The following 4 fields are treated as metadata/auxiliary rather than
portfolio-allocation categories:

- `fonKodu`
- `fonUnvan`
- `tarih`
- `bilFiyat`

This leaves 54 observed portfolio-allocation raw fields.

## Verification methodology

- Raw `dagilimSiraliGetirT` data was collected for `2026-08-11`.
- Candidate funds with non-null/non-zero unresolved fields were identified.
- The same fund/date was opened in the TEFAS `Fon Varlık Dağılımı` UI.
- A mapping was marked verified only when the raw numeric value matched the
  displayed TEFAS asset label and percentage.
- No abbreviation was decoded only from its name.

## Verified mappings

| Raw field | TEFAS asset label | Verification status |
|---|---|---|
| `hs` | Hisse Senedi | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `gyy` | Gayrimenkul Yatırımları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `gsyy` | Girişim Sermayesi Yatırımları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `yyf` | Yatırım Fonları Katılma Payları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `tr` | Ters-Repo | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `vmtl` | Mevduat (TL) | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `dt` | Devlet Tahvili | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `fb` | Finansman Bonosu | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `vdm` | Varlığa Dayalı Menkul Kıymetler | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `ost` | Özel Sektör Tahvili | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `tpp` | Takasbank Para Piyasası | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `kkstl` | Kamu Kira Sertifikaları (TL) | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `osks` | Özel Sektör Kira Sertifikaları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `gsykb` | Girişim Sermayesi Yatırım Fonları Katılma Payları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `gykb` | Gayrimenkul Yatırım Fonları Katılma Payları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `byf` | Borsa Yatırım Fonları Katılma Payları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `d` | Diğer | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `kba` | Kamu Dış Borçlanma Araçları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `khd` | Katılma Hesabı (Döviz) | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `kksd` | Kamu Kira Sertifikaları (Döviz) | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `kibd` | Döviz Cinsi Kamu İç Borçlanma Araçları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `vmd` | Mevduat (Döviz) | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `ybosb` | Yabancı Özel Sektör Borçlanma Araçları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `osdb` | Özel Sektör Dış Borçlanma Araçları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `km` | Kıymetli Madenler | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `kmbyf` | Kıymetli Madenler Cinsinden BYF | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `kmkba` | Kıymetli Madenler Cinsinden İhraç Edilen Kamu Borçlanma Araçları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `kmkks` | Kıymetli Madenler Cinsinden İhraç Edilen Kamu Kira Sertifikaları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `vint` | Vadeli İşlemler Nakit Teminatları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `yhs` | Yabancı Hisse Senedi | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `btas` | BİST Taahhütlü İşlem Pazarı Satım | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `khau` | Katılma Hesabı (Altın) | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `khtl` | Katılma Hesabı (TL) | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `ybyf` | Yabancı Borsa Yatırım Fonları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `hb` | Hazine Bonosu | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `r` | Repo | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `oksyd` | Özel Sektör Yurt Dışı Kira Sertifikaları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `gas` | Gayri Menkul Sertifikası | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `bpp` | Borsa İstanbul Para Piyasası | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `ybkb` | Yabancı Kamu Borçlanma Araçları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `kksyd` | Kamu Yurt Dışı Kira Sertifikaları | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `btaa` | BİST Taahhütlü İşlem Pazarı Alım | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |
| `vmau` | Mevduat (Altın) | `VERIFIED_SAME_DATE_RAW_UI_MATCH` |

## Remaining unresolved fields

| Raw field | Status |
|---|---|
| `bb` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `db` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `dot` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `eut` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `fkb` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `kh` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `kks` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `t` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `vm` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `yba` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |
| `ymk` | `UNRESOLVED_NO_ACTIVE_SAMPLE` |

These fields are present in the observed raw TEFAS schema, but no usable
non-null/non-zero example was found during our discovery scan, so their
business labels have not been verified.

## Important implementation notes

1. Portfolio values can be negative.
   Verified examples include:
   - `r` / Repo
   - `bpp` / Borsa İstanbul Para Piyasası

   Future ingestion and validation must not automatically reject, clamp, or
   convert negative portfolio-allocation values to zero.

2. Null and zero values are common and should remain distinct from an
   unsupported or missing raw field.

3. Raw abbreviations should be mapped through an explicit mapping layer in
   production rather than exposing abbreviations such as `hs`, `vmd`, `kmkks`,
   and similar raw keys directly to frontend or API consumers.

4. The 11 unresolved fields must remain supported as unknown raw fields until
   verified evidence is obtained.

## Discovery status

- 43 of 54 observed allocation fields are verified.
- 11 of 54 remain unresolved due to lack of an active verification sample.
- This is sufficient to model the currently observed active allocation data,
  while preserving unresolved raw fields for future discovery.
