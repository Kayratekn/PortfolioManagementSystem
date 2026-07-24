# Portfolio Management System

## Project Structure

```text
src/
├── config/         # Uygulama yapılandırmaları
├── controller/     # HTTP isteklerini karşılayan katman
├── exception/      # Hata sınıfları ve merkezi hata yönetimi
├── mapper/         # Model, request ve response dönüşümleri
├── model/          # Domain ve veri modelleri
├── repositories/  # Veri erişim katmanı
├── request/        # API istek modelleri
├── response/       # API cevap modelleri
└── services/       # İş kuralları ve servis katmanı
tests/              # Test dosyaları
```

## Layer Flow

```text
Request -> Controller -> Service -> Repository -> Model
                         |
                         v
                      Response
```

