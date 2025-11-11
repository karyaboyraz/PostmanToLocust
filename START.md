# Projeyi Başlatma Kılavuzu

Bu kılavuz, PostmanToLocust projesini çalıştırmak için gereken tüm komutları içerir.

## Hızlı Başlangıç

### 1. Sanal Ortamı Aktifleştir

**Linux/Mac:**
```bash
cd /Users/karyaboyraz/Documents/GitHub/PostmanToLocust
source venv/bin/activate
```

**Windows:**
```bash
cd path\to\PostmanToLocust
venv\Scripts\activate.bat
```

### 2. Servisleri Başlat

Projeyi çalıştırmak için 3 servisi başlatmanız gerekir. Her servisi **ayrı bir terminal penceresinde** çalıştırın.

#### Terminal 1: Locust (Load Test)

**Web UI ile (Önerilen):**
```bash
cd /Users/karyaboyraz/Documents/GitHub/PostmanToLocust
source venv/bin/activate
locust -f locustfile.py --config locust.conf --host=https://www.obilet.com
```

**Headless Mod (Web UI olmadan):**
```bash
cd /Users/karyaboyraz/Documents/GitHub/PostmanToLocust
source venv/bin/activate
locust -f locustfile.py --config locust.conf --headless --host=https://www.obilet.com
```

**Erişim:** http://localhost:8089

#### Terminal 2: Prometheus (Metrik Toplama)

```bash
cd /Users/karyaboyraz/Documents/GitHub/PostmanToLocust
prometheus --config.file=prometheus.yml --storage.tsdb.path=prometheus_data --web.listen-address=:9090
```

**Erişim:** http://localhost:9090

#### Terminal 3: Grafana (Görselleştirme)

**macOS (Homebrew ile):**
```bash
brew services start grafana
```

**Linux:**
```bash
sudo systemctl start grafana-server
```

**Docker ile:**
```bash
docker run -d -p 3000:3000 --name=grafana grafana/grafana
```

**Erişim:** http://localhost:3000 (admin/admin)

## Tam Komut Seti

### Adım 1: Sanal Ortamı Aktifleştir
```bash
cd /Users/karyaboyraz/Documents/GitHub/PostmanToLocust
source venv/bin/activate
```

### Adım 2: Locust'ı Başlat
```bash
locust -f locustfile.py --config locust.conf --host=https://www.obilet.com
```

### Adım 3: Prometheus'u Başlat (Yeni Terminal)
```bash
cd /Users/karyaboyraz/Documents/GitHub/PostmanToLocust
prometheus --config.file=prometheus.yml --storage.tsdb.path=prometheus_data --web.listen-address=:9090
```

### Adım 4: Grafana'yı Başlat (Yeni Terminal)
```bash
brew services start grafana
```

## Test Çalıştırma

### Web UI ile Test

1. **Locust Web UI'ı aç:** http://localhost:8089
2. **Test parametrelerini ayarla:**
   - Number of users: 10 (veya istediğiniz sayı)
   - Spawn rate: 2 (saniyede kaç kullanıcı)
   - Host: Test edilecek API URL'i
3. **"Start swarming" butonuna tıkla**
4. **Grafana'da sonuçları görüntüle:** http://localhost:3000

### Headless Mod ile Test

```bash
locust -f locustfile.py --config locust.conf --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 60s \
  --host=https://www.obilet.com
```

## Konfigürasyon Dosyası (locust.conf)

Mevcut ayarlar:
- **users**: 1000 (maksimum kullanıcı sayısı)
- **spawn-rate**: 100 (saniyede başlatılan kullanıcı)
- **run-time**: 10s (test süresi)
- **headless**: false (web UI aktif)
- **test-type**: client (api veya client)

## Servisleri Durdurma

### Locust
```bash
# Terminal'de Ctrl+C
```

### Prometheus
```bash
# Terminal'de Ctrl+C
# veya
pkill prometheus
```

### Grafana
```bash
# macOS
brew services stop grafana

# Linux
sudo systemctl stop grafana-server

# Docker
docker stop grafana
```

## Hızlı Kontrol Komutları

### Locust Metrics Endpoint
```bash
curl http://localhost:8089/metrics
```

### Prometheus Query
```bash
curl "http://localhost:9090/api/v1/query?query=locust_requests_total"
```

### Prometheus Target Durumu
```bash
curl "http://localhost:9090/api/v1/targets" | python3 -m json.tool
```

### Port Kontrolleri
```bash
# Locust portu (8089)
lsof -ti:8089

# Prometheus portu (9090)
lsof -ti:9090

# Grafana portu (3000)
lsof -ti:3000
```

## Sorun Giderme

### Locust Başlamıyorsa
```bash
# Port kullanımda mı kontrol et
lsof -ti:8089

# Sanal ortam aktif mi kontrol et
which python
# venv/bin/python görünmeli

# Bağımlılıkları kontrol et
pip list | grep locust
```

### Prometheus Başlamıyorsa
```bash
# Prometheus yüklü mü kontrol et
which prometheus

# Config dosyası doğru mu kontrol et
promtool check config prometheus.yml
```

### Grafana Başlamıyorsa
```bash
# Grafana servisi durumu
brew services list | grep grafana

# Logları kontrol et
brew services info grafana
```

## Örnek Kullanım Senaryoları

### Senaryo 1: Hızlı Test (10 kullanıcı, 30 saniye)
```bash
locust -f locustfile.py --config locust.conf --headless \
  --users 10 \
  --spawn-rate 2 \
  --run-time 30s \
  --host=https://www.obilet.com
```

### Senaryo 2: Yoğun Test (1000 kullanıcı, 5 dakika)
```bash
locust -f locustfile.py --config locust.conf --headless \
  --users 1000 \
  --spawn-rate 100 \
  --run-time 5m \
  --host=https://www.obilet.com
```

### Senaryo 3: Web UI ile İnteraktif Test
```bash
locust -f locustfile.py --config locust.conf --host=https://www.obilet.com
```
Sonra http://localhost:8089 adresinden testi başlatın.

## Notlar

- Tüm servislerin çalıştığından emin olun
- Grafana dashboard'u import etmeyi unutmayın
- Test çalıştırmadan önce Prometheus'un Locust'tan metrik topladığını kontrol edin
- Metrikler test başladıktan sonra görünmeye başlar

## İletişim

Sorularınız için: [GitHub Issues](https://github.com/karyaboyraz/PostmanToLocust/issues)

