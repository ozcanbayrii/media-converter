# Media Converter

[English](README.md) · **Türkçe**

**YouTube**, **Instagram** ve **TikTok** için kendi sunucunuzda barındırabileceğiniz (self-hosted), minimalist **MP4 & MP3 medya dönüştürücü** — hem mobil uyumlu web uygulaması hem de yerel Windows masaüstü uygulaması (`.exe`) olarak kullanılabilir.

Canlı demo: **[converter.ozcan.work](https://converter.ozcan.work)**

---

## Özellikler

- **Çoklu platform desteği:** YouTube (videolar ve Shorts), Instagram (Reels ve gönderiler), TikTok (`curl_cffi` TLS impersonation ile filigransız indirme) ve `yt-dlp` tarafından desteklenen diğer platformlar.
- **Format ve kalite seçimi:**
  - **MP4 Video:** En İyi (Otomatik), `1080p`, `720p`, `480p`
  - **MP3 Ses:** `320 kbps`, `256 kbps`, `192 kbps`, `128 kbps`
- **Minimalist monokrom arayüz:** Kırık siyah (`#121213`) karanlık tema ve sıcak kırık beyaz (`#F3F2EE`) aydınlık tema; cihaz temasını otomatik algılar ve tek tıkla değiştirilebilir.
- **Çift dil desteği (`EN` / `TR`):** İlk açılışta tarayıcı veya işletim sistemi dilini otomatik algılar; uygulama içinden anlık değiştirilebilir.
- **Web Uygulaması (`web/`):** Mobil uyumlu Flask arka ucu, anlık ilerleme takibi, manuel indirme kontrolü, Docker desteği ve 30 dakika sonra otomatik geçici dosya temizliği.
- **Masaüstü Uygulaması (`desktop/`):** Windows'un yerel WebView2 motorunu kullanan (`pywebview`) hafif masaüstü uygulaması; Windows 11 karanlık/aydınlık başlık çubuğu senkronizasyonu, yerel klasör seçici, kalıcı ayarlar, tek tıkla dosyayı açma / Explorer'da gösterme ve tek dosya `.exe` derleme betiği.

---

## Proje Yapısı

```text
media-converter/
├── web/                     # Web uygulaması (Flask + Docker)
│   ├── server.py            # API sunucusu, yt-dlp işleyicisi ve otomatik temizlik
│   ├── templates/
│   │   └── index.html       # Responsive monokrom arayüz (TR/EN, Karanlık/Aydınlık)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── VPS_KURULUM.md       # VPS kurulum ve SSL rehberi
├── desktop/                 # Windows masaüstü uygulaması (pywebview)
│   ├── main.py              # Masaüstü arka ucu ve Win32 pencere entegrasyonu
│   ├── ui/
│   │   ├── index.html       # Monokrom masaüstü arayüzü (TR/EN, Karanlık/Aydınlık)
│   │   └── icon.png
│   ├── assets/
│   │   ├── app.ico
│   │   └── icon.png
│   ├── build.py             # PyInstaller tek dosya .exe derleyicisi
│   └── requirements.txt
├── README.md                # İngilizce dokümantasyon
├── README.tr.md             # Türkçe dokümantasyon
└── LICENSE
```

---

## Gereksinimler

- **Python** 3.11+
- **FFmpeg** (`PATH` üzerinde erişilebilir olmalıdır — MP3 dönüştürme ve HD MP4 birleştirme için gereklidir)
- **Node.js** (`yt-dlp` üzerinden YouTube JS doğrulamaları için önerilir)

---

## Hızlı Başlangıç — Web Uygulaması

### 1. Yöntem: Docker Compose (Önerilen)

```bash
cd web
docker compose up -d --build
```

Uygulama `http://localhost:5000` adresinde çalışacaktır. Detaylı VPS + Nginx + SSL kurulumu için [web/VPS_KURULUM.md](web/VPS_KURULUM.md) dosyasına bakabilirsiniz.

### 2. Yöntem: Python ile Yerel Çalıştırma

```bash
cd web
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
python server.py
```

Varsayılan olarak `5050` portunda çalışır (`PORT` ortam değişkeniyle değiştirilebilir): `http://localhost:5050`.

---

## Hızlı Başlangıç — Windows Masaüstü Uygulaması

### Kaynak koddan çalıştırma

```bash
cd desktop
pip install -r requirements.txt
python main.py
```

### Tek parça `.exe` derleme

```bash
cd desktop
python build.py
```

İşlem sonunda `desktop/dist/MediaConverter.exe` konumunda siyah konsol penceresi açmayan, doğrudan çalıştırılabilir uygulama üretilir.

---

## Lisans

MIT Lisansı — detaylar için [LICENSE](LICENSE) dosyasına bakın.
