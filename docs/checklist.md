# AlarmDecoder WebApp Integration Checklist

✅ This checklist walks you through deploying `alarmdecoder-webapp` with the core `alarmdecoder` library on a Raspberry Pi using Docker.

---

## 🔧 1. Raspberry Pi Host Setup

- [ ] Enable serial port hardware (e.g. `/dev/ttyAMA0`)
  ```bash
  sudo raspi-config
  # -> Interface Options -> Serial -> "No" to shell, "Yes" to serial hardware
  ```

- [ ] Add your user to the `dialout` group:
  ```bash
  sudo usermod -a -G dialout $USER
  ```

- [ ] Verify serial device exists:
  ```bash
  ls -l /dev/ttyAMA0
  ```

---

## 🐳 2. Docker Setup

- [ ] Install Docker + Docker Compose:
  ```bash
  curl -sSL https://get.docker.com | sh
  sudo usermod -aG docker $USER
  ```

- [ ] Use `docker-compose.yml` and `.env` to mount `/dev/ttyAMA0`:
  ```yaml
  devices:
    - "/dev/ttyAMA0:/dev/ttyAMA0"
  ```

---

## ⚙️ 3. Software Setup

- [ ] Install `alarmdecoder` Python library in container (via `setup.py` or `pip`)
- [ ] Install `ser2sock` for TCP socket mode (optional)
- [ ] Configure:
  - `device_type`: `serial`
  - `device_path`: `/dev/ttyAMA0`
  - `use_ssl`: `false` or `true` if using certs

---

## 🔐 4. Certificates (Optional)

- [ ] Enable SSL in settings (`use_ssl: true`)
- [ ] Generate CA, Server, Internal certs via `/settings/certificates/generateCA`
- [ ] Copy certs to `/etc/ser2sock/certs`
- [ ] Ensure `.env` has:
  ```bash
  SER2SOCK_CONFIG_PATH=/etc/ser2sock
  BOUNCYCASTLE_JAR_PATH=/opt/bcprov-jdk15on-146.jar
  ```

---

## 🚦 5. Testing

- [ ] Run `docker-compose up`
- [ ] Visit `http://<raspberrypi.local>:5000`
- [ ] Log in as `admin`, configure zones, certs, and notifications

---

## 🧪 Useful Commands

```bash
# Reset DB
docker compose exec alarmdecoder-webapp flask initdb --drop

# Rebuild
docker compose build

# Logs
docker compose logs -f
```

---

✅ You're now running AlarmDecoder WebApp securely on a Raspberry Pi!
