# Production deployment

1. Uygulamayı `/var/www/linguaflow` altına koyun, `.env.example` dosyasını `.env` olarak kopyalayın ve `APP_ENV=production` yapın.
2. `deploy/linguaflow.service` dosyasını `/etc/systemd/system/` altına koyup `systemctl enable --now linguaflow` çalıştırın.
3. `deploy/Caddyfile` içindeki domain'i değiştirip Caddy'yi yeniden başlatın. Caddy HTTPS sertifikasını otomatik alır.
4. `deploy/backup.sh` dosyasını günlük cron/systemd timer ile çalıştırın.
5. Firewall'da yalnızca 22, 80 ve 443 portlarını açık bırakın; 8000'i dışarı açmayın.
