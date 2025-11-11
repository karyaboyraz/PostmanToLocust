# Grafana ve Prometheus Entegrasyonu

## Durum
✅ Prometheus Locust'tan metrikleri topluyor  
✅ Grafana Prometheus'a bağlı  
✅ Dashboard oluşturuldu ve yapılandırıldı  

## Erişim
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Locust**: http://localhost:8089
- **Locust Metrics**: http://localhost:8089/metrics

## Test Verisi Oluşturma

### Adım 1: Locust'ta Test Başlat
1. Tarayıcıda http://localhost:8089 adresine git
2. Number of users: 10 (veya istediğin sayı)
3. Spawn rate: 2 (saniyede kaç kullanıcı başlatılacak)
4. Host: Test edilecek API URL'i (örn: http://localhost:8000)
5. "Start swarming" butonuna tıkla

### Adım 2: Grafana'da Verileri Görüntüle
1. Tarayıcıda http://localhost:3000 adresine git
2. Sol menüden "Dashboards" > "Locust Performance Metrics" seç
3. Metrikler otomatik olarak görüntülenecek

## Mevcut Metrikler

### Temel Metrikler
- `locust_users_current`: Aktif kullanıcı sayısı
- `locust_requests_total`: Toplam istek sayısı
- `locust_requests_failures_total`: Başarısız istek sayısı
- `locust_requests_per_second`: Saniyedeki istek sayısı (RPS)

### Response Time Metrikleri
- `locust_response_time_median_seconds`: Medyan yanıt süresi
- `locust_response_time_p95_seconds`: 95. percentile yanıt süresi
- `locust_response_time_p99_seconds`: 99. percentile yanıt süresi
- `locust_response_time_seconds`: Summary metrik (quantile'lar ile)

## Dashboard Panelleri

1. **Requests per Second**: Saniyedeki istek sayısı
2. **Total Requests**: Toplam istek sayısı
3. **Response Time (p95, median, p99)**: Yanıt süreleri
4. **Failed Requests**: Başarısız istekler
5. **Current Users**: Aktif kullanıcı sayısı
6. **Failure Rate**: Başarısızlık oranı

## Sorun Giderme

### Grafana'da Veri Görünmüyorsa

1. **Prometheus'ta metrikler var mı kontrol et:**
   ```bash
   curl "http://localhost:9090/api/v1/query?query=locust_requests_total"
   ```

2. **Locust metrics endpoint çalışıyor mu kontrol et:**
   ```bash
   curl http://localhost:8089/metrics
   ```

3. **Prometheus target durumu:**
   ```bash
   curl "http://localhost:9090/api/v1/targets" | python3 -m json.tool
   ```
   Target'ın "health": "up" olması gerekir

4. **Locust'ta test çalıştırıldı mı kontrol et:**
   - Locust web arayüzünde test başlatılmış olmalı
   - http://localhost:8089/stats/requests adresinde veri olmalı

### Prometheus Target Down İse

1. Locust'un çalıştığından emin ol:
   ```bash
   lsof -ti:8089
   ```

2. Metrics endpoint'e erişilebilir mi kontrol et:
   ```bash
   curl http://localhost:8089/metrics
   ```

3. Prometheus'u yeniden başlat:
   ```bash
   pkill prometheus
   prometheus --config.file=prometheus.yml --storage.tsdb.path=prometheus_data --web.listen-address=:9090
   ```

## Servisleri Başlatma

### Locust
```bash
cd /Users/karyaboyraz/Documents/GitHub/PostmanToLocust
source venv/bin/activate
locust -f locustfile.py --config locust.conf --host=http://localhost
```

### Prometheus
```bash
prometheus --config.file=prometheus.yml --storage.tsdb.path=prometheus_data --web.listen-address=:9090
```

### Grafana
```bash
brew services start grafana
```

## Notlar

- Prometheus 5 saniyede bir metrikleri toplar
- Grafana dashboard 5 saniyede bir yenilenir
- Test çalıştırmadan önce Locust'ta test başlatılmalı
- Metrikler test çalıştırıldıktan sonra görünmeye başlar

