# PRD — Jiyu Home Server Dashboard
**Project:** Personal Home Server Monitoring Dashboard  
**Stack:** FastAPI (Python) + Next.js 15  
**Author:** Erlangga (jiyu)  
**Version:** 1.0

---

## 1. Overview

A self-hosted web dashboard untuk monitoring home server (Fedora Linux) secara realtime. Dashboard ini menggantikan Cockpit dengan UI custom bergaya **dark neumorphism** — soft shadows, dark gray base, monospace numbers, dan smooth animations.

---

## 2. Goals

- Monitor resource usage server (CPU, RAM, disk, network) secara realtime
- Manage running processes (view + kill)
- Manage systemd services (view status + start/stop/restart)
- Akses dari browser device manapun di jaringan lokal

---

## 3. Tech Stack

### Backend
- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Library:** `psutil` (system stats), `subprocess` (systemctl commands)
- **Server:** Uvicorn
- **Port:** `8000`
- **Host:** `0.0.0.0` (accessible dari network)

### Frontend
- **Framework:** Next.js 15 (App Router)
- **Styling:** Tailwind CSS
- **Font:** JetBrains Mono (numbers/stats) + Syne (UI text)
- **Data fetching:** `setInterval` every 3 seconds (no WebSocket needed)
- **Port:** `3000`

---

## 4. Design System

### Style: Dark Neumorphism
- **Base color:** `#1e1e2e` (dark gray-purple)
- **Shadow light:** `#2a2a3e`
- **Shadow dark:** `#12121e`
- **Accent:** `#7c6aff` (soft purple)
- **Success:** `#4ade80`
- **Warning:** `#facc15`
- **Danger:** `#f87171`
- **Text primary:** `#e2e8f0`
- **Text secondary:** `#94a3b8`

### Neumorphism Shadow Formula
```css
/* Raised element */
box-shadow: 6px 6px 12px #12121e, -6px -6px 12px #2a2a3e;

/* Pressed/inset element */
box-shadow: inset 4px 4px 8px #12121e, inset -4px -4px 8px #2a2a3e;
```

### Typography
- Stats numbers: `JetBrains Mono` — bold, monospace
- Labels & UI: `Syne` — clean, modern
- Font size scale: 12px / 14px / 16px / 24px / 32px / 48px

### Animations
- Stat number changes: smooth counter animation (ease-out, 500ms)
- Page transitions: fade + slide up (300ms)
- Progress bars: smooth width transition (800ms ease)
- Service status badge: pulse animation when running

---

## 5. Pages & Features

### 5.1 Page: Dashboard (`/`)

**Layout:** Bento grid — 4 stat cards di atas, 2 chart/detail di bawah

**Components:**

**Stat Cards (4 cards):**
| Card | Data | Detail |
|------|------|--------|
| CPU Usage | Persentase (%) | Core count, frequency |
| RAM Usage | Used / Total (GB) | Persentase bar |
| Disk Usage | Used / Total (GB) | Persentase bar |
| Network | In / Out (MB/s) | Total sent/received |

**Additional Info:**
- Server uptime (format: `X days, HH:MM:SS`)
- Hostname & OS info
- Current time server

**Behavior:**
- Auto-fetch `/stats` setiap 3 detik
- Progress bar animasi smooth saat nilai berubah
- Warna bar: hijau (<60%), kuning (60-80%), merah (>80%)

---

### 5.2 Page: Processes (`/processes`)

**Layout:** Full-width table dengan search bar di atas

**Columns:**
| Column | Data |
|--------|------|
| PID | Process ID |
| Name | Process name |
| CPU % | CPU usage |
| RAM % | Memory usage |
| RAM MB | Memory in MB |
| Status | running/sleeping/zombie |
| Action | Kill button |

**Features:**
- Search/filter by process name
- Sort by CPU% atau RAM% (descending default)
- Kill process button → confirm dialog sebelum kill
- Auto-refresh setiap 3 detik
- Max tampilkan 50 processes teratas (sorted by CPU%)

**Kill Process Flow:**
1. User klik tombol Kill (merah)
2. Muncul confirm dialog: `"Kill process [name] (PID: [pid])?"` 
3. Confirm → `DELETE /processes/{pid}`
4. Toast notification: sukses/gagal

---

### 5.3 Page: Services (`/services`)

**Layout:** Grid cards, 2-3 kolom

**Services yang dimonitor:**
- `sshd` — SSH Server
- `cockpit.socket` — Cockpit Web Console
- `docker` — Docker Engine  
- `nginx` — Nginx Web Server
- `firewalld` — Firewall

**Card per Service:**
- Nama service (human-readable)
- Status badge: `● Running` (hijau) / `○ Stopped` (merah) / `⟳ Loading` (kuning)
- Tombol aksi: **Start** / **Stop** / **Restart**
- Disable tombol sesuai state (misal: Running → disable Start, enable Stop)

**Behavior:**
- Auto-refresh setiap 5 detik
- Loading state saat action sedang dijalankan
- Toast notification setelah action selesai

---

## 6. API Endpoints (Backend)

### Base URL: `http://192.168.18.245:8000`

#### `GET /stats`
Returns system statistics.
```json
{
  "cpu": {
    "percent": 23.5,
    "cores": 4,
    "frequency_mhz": 2400
  },
  "ram": {
    "total_gb": 4.0,
    "used_gb": 2.1,
    "percent": 52.5
  },
  "disk": {
    "total_gb": 931.5,
    "used_gb": 12.3,
    "percent": 1.3
  },
  "network": {
    "bytes_sent_mb": 1024.5,
    "bytes_recv_mb": 2048.3,
    "sent_speed_mbps": 0.5,
    "recv_speed_mbps": 1.2
  },
  "uptime_seconds": 86400,
  "uptime_str": "1 day, 00:00:00",
  "hostname": "fedora",
  "os": "Fedora Linux 42"
}
```

#### `GET /processes`
Returns list of top 50 processes sorted by CPU%.
```json
[
  {
    "pid": 1234,
    "name": "python3",
    "cpu_percent": 5.2,
    "memory_percent": 1.3,
    "memory_mb": 52.4,
    "status": "running"
  }
]
```

#### `DELETE /processes/{pid}`
Kill a process by PID.
```json
{ "success": true, "message": "Process 1234 killed" }
```

#### `GET /services`
Returns status of monitored services.
```json
[
  {
    "name": "sshd",
    "display_name": "SSH Server",
    "status": "running",
    "enabled": true
  }
]
```

#### `POST /services/{name}/action`
Start, stop, or restart a service.
```json
// Request body:
{ "action": "restart" }

// Response:
{ "success": true, "message": "sshd restarted successfully" }
```

---

## 7. Project Structure

```
dashboard/
├── backend/
│   ├── main.py          # FastAPI app
│   ├── requirements.txt # psutil, fastapi, uvicorn
│   └── .env             # Config (port, allowed origins)
│
└── frontend/
    ├── app/
    │   ├── page.tsx           # Dashboard
    │   ├── processes/
    │   │   └── page.tsx       # Processes
    │   ├── services/
    │   │   └── page.tsx       # Services
    │   ├── layout.tsx         # Root layout + navbar
    │   └── globals.css        # Neumorphism CSS vars
    ├── components/
    │   ├── StatCard.tsx       # Reusable stat card
    │   ├── ProgressBar.tsx    # Animated progress bar
    │   ├── ServiceCard.tsx    # Service status card
    │   ├── Navbar.tsx         # Navigation
    │   └── Toast.tsx          # Notification toast
    ├── lib/
    │   └── api.ts             # API fetch functions
    └── .env.local             # NEXT_PUBLIC_API_URL
```

---

## 8. Environment Variables

### Backend `.env`
```
PORT=8000
ALLOWED_ORIGINS=http://localhost:3000,http://192.168.18.245:3000
```

### Frontend `.env.local`
```
NEXT_PUBLIC_API_URL=http://192.168.18.245:8000
```

---

## 9. Navigation

Navbar sticky di atas dengan 3 links:
- `🖥️ Dashboard` → `/`
- `⚙️ Processes` → `/processes`
- `🔧 Services` → `/services`

Active state: neumorphism inset shadow pada link aktif.

---

## 10. Error Handling

- Jika backend tidak bisa direach → tampilkan banner `"Server offline"` berwarna merah
- Jika kill process gagal (permission denied) → toast error
- Jika service action gagal → toast error dengan pesan dari backend
- Loading skeleton saat data pertama kali di-fetch

---

## 11. Deployment

### Backend (di laptop server via SSH):
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Untuk production (auto-start):
```bash
# Buat systemd service agar backend auto-start saat boot
sudo nano /etc/systemd/system/dashboard-backend.service
```

### Frontend:
- Development: `npm run dev` di laptop utama
- Production: deploy ke Vercel (frontend only, backend tetap lokal)