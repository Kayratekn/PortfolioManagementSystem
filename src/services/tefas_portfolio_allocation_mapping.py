from __future__ import annotations

VERIFIED_ALLOCATION_LABELS: dict[str, str] = {
    "hs": "Hisse Senedi",
    "gyy": "Gayrimenkul Yatırımları",
    "gsyy": "Girişim Sermayesi Yatırımları",
    "yyf": "Yatırım Fonları Katılma Payları",
    "tr": "Ters-Repo",
    "vmtl": "Mevduat (TL)",
    "dt": "Devlet Tahvili",
    "fb": "Finansman Bonosu",
    "vdm": "Varlığa Dayalı Menkul Kıymetler",
    "ost": "Özel Sektör Tahvili",
    "tpp": "Takasbank Para Piyasası",
    "kkstl": "Kamu Kira Sertifikaları (TL)",
    "osks": "Özel Sektör Kira Sertifikaları",
    "gsykb": "Girişim Sermayesi Yatırım Fonları Katılma Payları",
    "gykb": "Gayrimenkul Yatırım Fonları Katılma Payları",
    "byf": "Borsa Yatırım Fonları Katılma Payları",
    "d": "Diğer",
    "kba": "Kamu Dış Borçlanma Araçları",
    "khd": "Katılma Hesabı (Döviz)",
    "kksd": "Kamu Kira Sertifikaları (Döviz)",
    "kibd": "Döviz Cinsi Kamu İç Borçlanma Araçları",
    "vmd": "Mevduat (Döviz)",
    "ybosb": "Yabancı Özel Sektör Borçlanma Araçları",
    "osdb": "Özel Sektör Dış Borçlanma Araçları",
    "km": "Kıymetli Madenler",
    "kmbyf": "Kıymetli Madenler Cinsinden BYF",
    "kmkba": "Kıymetli Madenler Cinsinden İhraç Edilen Kamu Borçlanma Araçları",
    "kmkks": "Kıymetli Madenler Cinsinden İhraç Edilen Kamu Kira Sertifikaları",
    "vint": "Vadeli İşlemler Nakit Teminatları",
    "yhs": "Yabancı Hisse Senedi",
    "btas": "BİST Taahhütlü İşlem Pazarı Satım",
    "khau": "Katılma Hesabı (Altın)",
    "khtl": "Katılma Hesabı (TL)",
    "ybyf": "Yabancı Borsa Yatırım Fonları",
    "hb": "Hazine Bonosu",
    "r": "Repo",
    "oksyd": "Özel Sektör Yurt Dışı Kira Sertifikaları",
    "gas": "Gayri Menkul Sertifikası",
    "bpp": "Borsa İstanbul Para Piyasası",
    "ybkb": "Yabancı Kamu Borçlanma Araçları",
    "kksyd": "Kamu Yurt Dışı Kira Sertifikaları",
    "btaa": "BİST Taahhütlü İşlem Pazarı Alım",
    "vmau": "Mevduat (Altın)",
}

UNRESOLVED_ALLOCATION_FIELDS: frozenset[str] = frozenset(
    {
        "bb",
        "db",
        "dot",
        "eut",
        "fkb",
        "kh",
        "kks",
        "t",
        "vm",
        "yba",
        "ymk",
    }
)

EXPECTED_ALLOCATION_FIELDS: frozenset[str] = frozenset(
    set(VERIFIED_ALLOCATION_LABELS) | set(UNRESOLVED_ALLOCATION_FIELDS)
)


def get_allocation_label(raw_field_name: str) -> str | None:
    return VERIFIED_ALLOCATION_LABELS.get(raw_field_name)


def get_mapping_status(raw_field_name: str) -> str:
    if raw_field_name in VERIFIED_ALLOCATION_LABELS:
        return "VERIFIED"
    if raw_field_name in UNRESOLVED_ALLOCATION_FIELDS:
        return "UNRESOLVED"
    raise ValueError(f"Unknown TEFAS allocation raw field: {raw_field_name}")
