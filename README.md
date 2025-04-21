# PostmanToLocust

Bu proje, Postman koleksiyonlarını kullanarak Locust yük testi senaryoları oluşturmanızı sağlayan bir araçtır. Postman koleksiyonlarınızı doğrudan projeye ekleyerek, bu koleksiyonları temel alan yük testleri oluşturabilirsiniz.

## Özellikler

- Postman koleksiyonlarını doğrudan kullanma
- HTTP isteklerini ve yanıtlarını destekleme
- Dinamik değişken desteği
- Çoklu istek senaryoları oluşturma
- Kolay kurulum ve kullanım

## Gereksinimler

- Python 3.8 veya üzeri
- pip (Python paket yöneticisi)
- Postman koleksiyonu (JSON formatında)

## Kurulum

1. Projeyi klonlayın:
```bash
git clone https://github.com/karyaboyraz/PostmanToLocust.git
cd PostmanToLocust
```

2. Sanal ortam oluşturun ve aktifleştirin:

Linux/Mac için:
```bash
python3 -m venv venv
source venv/bin/activate
```

Windows için:

Adım 1: Python Kurulumu
- Python'u yükleyin (eğer yüklü değilse)
- https://www.python.org/downloads/ adresinden indirin
- Kurulum sırasında "Add Python to PATH" seçeneğini işaretleyin

Adım 2: Sanal Ortam Oluşturma
```bash
# Komut İstemcisi (CMD) veya PowerShell'de:
python -m venv venv
```

Adım 3: Sanal Ortamı Aktifleştirme

Komut İstemcisi (CMD) için:
```bash
# 1. Komut İstemcisini yönetici olarak açın
# 2. Proje dizinine gidin
cd path\to\PostmanToLocust
# 3. Sanal ortamı aktifleştirin
venv\Scripts\activate.bat
```

## Kullanım

1. Postman koleksiyonunuzu JSON formatında dışa aktarın ve `collections` klasörüne ekleyin.

2. Projeyi çalıştırın:
```bash
locust -f locustfile.py
```

## İletişim

Proje Sahibi - [@karyaboyraz](https://github.com/karyaboyraz)

Proje Linki: [https://github.com/karyaboyraz/PostmanToLocust](https://github.com/karyaboyraz/PostmanToLocust)