# 🌐 Medya Dönüştürücü VPS Kurulum Rehberi

Bu rehber, YouTube, Instagram ve TikTok MP4/MP3 dönüştürücüsünü bir VPS (Ubuntu/Debian sunucu) üzerine kurup telefonunuzdan veya bilgisayarınızdan **web sitesi gibi** her yerden erişmeniz için hazırlanmıştır.

Web dosyaları proje içindeki şu klasördedir:
📁 `./web`

---

## ⚡ 1. Yöntem: Docker ile Kurulum (EN BASİT VE ÖNERİLEN)

Docker sayesinde sunucuya Python veya FFmpeg kurmakla uğraşmazsınız. Her şey tek komutla hazır gelir.

### Adım 1: VPS'e Bağlanın
Terminal veya PuTTY ile sunucunuza bağlanın:
```bash
ssh root@vps_ip_adresiniz
```

### Adım 2: Docker ve Docker Compose Yükleyin (Yoksa)
```bash
curl -fsSL https://get.docker.com | sh
```

### Adım 3: Dosyaları Sunucuya Yükleyin
Bilgisayarınızdaki `web` klasörünün içindekileri VPS'e aktarın.
Örneğin bilgisayarınızdan SCP komutuyla:
```bash
scp -r ./web root@vps_ip_adresiniz:/root/converter
```
*(Veya WinSCP / FileZilla programı ile `/root/donusturucu` klasörüne sürükleyip bırakabilirsiniz.)*

### Adım 4: Başlatın
VPS içinde klasöre girip tek bir komut verin:
```bash
cd /root/donusturucu
docker compose up -d --build
```

🎉 **Hazır!** Artık tarayıcınızdan şu adrese girerek kullanabilirsiniz:
👉 `http://VPS_IP_ADRESINIZ:5000`

---

## 🐧 2. Yöntem: Dockersız (Doğrudan Ubuntu/Debian ile)

Docker kullanmak istemiyorsanız doğrudan Python servisi olarak da çalıştırabilirsiniz:

### Adım 1: VPS'e Gerekli Paketleri Kurun
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv ffmpeg nodejs git
```

### Adım 2: Projeyi Yükleyin ve Ortamı Hazırlayın
Klasöre gidin ve sanal ortam oluşturup paketleri kurun:
```bash
cd /root/donusturucu
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Adım 3: 7/24 Arka Planda Çalışması İçin Servis Oluşturun (systemd)
Sunucu yeniden başlasa bile otomatik açılması için:

```bash
sudo nano /etc/systemd/system/donusturucu.service
```

İçine şunları yapıştırın (CTRL+O -> Enter -> CTRL+X ile kaydedin):
```ini
[Unit]
Description=Medya Donusturucu Web Servisi
After=network.target

[Service]
User=root
WorkingDirectory=/root/donusturucu
ExecStart=/root/donusturucu/venv/bin/python server.py
Restart=always
Environment=PORT=5000

[Install]
WantedBy=multi-user.target
```

Servisi aktifleştirin ve başlatın:
```bash
sudo systemctl daemon-reload
sudo systemctl enable donusturucu
sudo systemctl start donusturucu
```

Durumunu kontrol etmek için:
```bash
sudo systemctl status donusturucu
```

---

## 🔒 Güvenlik Duvarı (Port 5000 İzni)
Eğer siteye bağlanamıyorsanız, VPS güvenlik duvarında 5000 portunu açın:
```bash
sudo ufw allow 5000/tcp
```
*(Oracle Cloud, AWS veya GCP gibi sağlayıcılar kullanıyorsanız, sağlayıcının web yönetim panelindeki "Security Groups / Firewall Rules" kısmından da Port 5000 için Ingress/Gelen kuralı eklemelisiniz.)*

---

## 🌐 3. (Opsiyonel) Kendi Domain Adınız ve Ücretsiz SSL (HTTPS)
Eğer `http://IP:5000` yerine `https://video.siteniz.com` gibi kullanmak isterseniz:

1. Domain DNS ayarlarınızdan bir A kaydı oluşturup VPS IP'nize yönlendirin.
2. Nginx kurun:
   ```bash
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```
3. Nginx ayarını yapın:
   ```bash
   sudo nano /etc/nginx/sites-available/donusturucu
   ```
   İçeriği:
   ```nginx
   server {
       server_name video.siteniz.com;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_read_timeout 600s;
           proxy_connect_timeout 600s;
           client_max_body_size 500M;
       }
   }
   ```
4. Aktif edin ve SSL alın:
   ```bash
   sudo ln -s /etc/nginx/sites-available/donusturucu /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   sudo certbot --nginx -d video.siteniz.com
   ```
Artık siteniz tüm cihazlardan **HTTPS** ile güvenle açılacaktır!
