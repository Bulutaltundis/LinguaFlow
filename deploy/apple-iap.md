# Apple IAP backend kurulumu

Uygulama StoreKit 2 ile satın alma yaptıktan sonra `transaction.jwsRepresentation` değerini oturum açmış kullanıcının şu endpoint'ine gönderir:

`POST /billing/apple/transaction`

```json
{"signed_transaction":"<StoreKit transaction.jwsRepresentation>"}
```

Backend, Apple App Store Server Library ile JWS'yi doğrular; product ID aylık/yıllık planlardan biri değilse entitlement vermez. Doğrulanan aktif işlem Super planı açar ve sınırsız heart sağlar.

Apple Developer hesabında App Store Server Notifications V2 URL'sini şu endpoint'e verin:

`https://alan-adiniz.com/billing/apple/notifications`

Sandbox için `APPLE_ENVIRONMENT=sandbox`, production için `production` kullanın. Apple Root Certificate dosyasını sunucuda static klasörünün dışında tutup `APPLE_ROOT_CERT_PATH` ile gösterin. `APPLE_MONTHLY_PRODUCT_ID` ve `APPLE_YEARLY_PRODUCT_ID`, App Store Connect'teki gerçek auto-renewable subscription product ID'leri olmalı.

İmzalı transaction doğrulaması için dependency kurulumu:

```bash
pip install app-store-server-library
```

Apple’ın eski `verifyReceipt` endpoint’i yerine StoreKit signed transaction veya App Store Server API/Notifications V2 kullanılması öneriliyor.
