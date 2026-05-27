import os
import psutil
import platform
import time
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import sqlite3
import asyncio
from datetime import datetime, timedelta
import contextlib

load_dotenv()

# --- Database Initialization ---
DB_FILE = "history.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resource_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                cpu_percent REAL,
                ram_percent REAL,
                disk_percent REAL
            )
        ''')
        conn.commit()

init_db()

# --- Background Task ---
async def log_stats_task():
    while True:
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            
            with contextlib.closing(sqlite3.connect(DB_FILE)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO resource_history (cpu_percent, ram_percent, disk_percent) VALUES (?, ?, ?)",
                    (cpu, ram, disk)
                )
                conn.commit()
        except Exception as e:
            print(f"Error logging stats: {e}")
            
        await asyncio.sleep(60)

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(log_stats_task())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(title="Jiyu Home Server Dashboard API", lifespan=lifespan)

origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOOT_TIME = psutil.boot_time()

# Mock services for Windows
MOCK_SERVICES = [
    {"name": "sshd", "display_name": "SSH Server", "status": "running", "enabled": True},
    {"name": "cockpit.socket", "display_name": "Cockpit Web Console", "status": "stopped", "enabled": False},
    {"name": "docker", "display_name": "Docker Engine", "status": "running", "enabled": True},
    {"name": "nginx", "display_name": "Nginx Web Server", "status": "running", "enabled": True},
    {"name": "firewalld", "display_name": "Firewall", "status": "running", "enabled": True}
]

def format_uptime(seconds: float) -> str:
    days = int(seconds // (24 * 3600))
    seconds = seconds % (24 * 3600)
    hours = int(seconds // 3600)
    seconds %= 3600
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}"

@app.get("/stats")
def get_stats():
    # CPU
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_cores = psutil.cpu_count(logical=False) or psutil.cpu_count()
    cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0

    # RAM
    ram = psutil.virtual_memory()
    
    # Disk
    disk = psutil.disk_usage('/')
    
    # Network
    net_io = psutil.net_io_counters()

    # Uptime
    uptime_seconds = time.time() - BOOT_TIME

    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": cpu_cores,
            "frequency_mhz": cpu_freq
        },
        "ram": {
            "total_gb": round(ram.total / (1024**3), 2),
            "used_gb": round(ram.used / (1024**3), 2),
            "percent": ram.percent
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "percent": disk.percent
        },
        "network": {
            "bytes_sent_mb": round(net_io.bytes_sent / (1024**2), 2),
            "bytes_recv_mb": round(net_io.bytes_recv / (1024**2), 2),
            "sent_speed_mbps": 0.0, # Not easily calculable statically without state
            "recv_speed_mbps": 0.0
        },
        "uptime_seconds": uptime_seconds,
        "uptime_str": format_uptime(uptime_seconds),
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}"
    }

@app.get("/history")
def get_history():
    # Fetch last 24 hours of data, or up to 1440 points (assuming 1/min)
    # Since we want a readable chart, maybe we return data aggregated or just the last N points.
    # We will return the last 60 points for the last hour to prevent overwhelming the chart,
    # or return all and let frontend handle it. Let's return the last 60 points.
    with contextlib.closing(sqlite3.connect(DB_FILE)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, cpu_percent as cpu, ram_percent as ram 
            FROM resource_history 
            ORDER BY timestamp DESC 
            LIMIT 60
        ''')
        rows = cursor.fetchall()
    
    # Reverse so it's chronological
    data = [dict(row) for row in reversed(rows)]
    
    # Format timestamp to HH:MM
    for row in data:
        try:
            dt = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
            row['time'] = dt.strftime('%H:%M')
        except:
            row['time'] = row['timestamp']
            
    return data

@app.get("/processes")
def get_processes():
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'status']):
        try:
            info = proc.info
            # For accurate cpu percent, normally need to call cpu_percent twice with delay
            # but for a quick list we'll just use what's returned
            mem_mb = info['memory_info'].rss / (1024 * 1024) if info['memory_info'] else 0
            processes.append({
                "pid": info['pid'],
                "name": info['name'],
                "cpu_percent": info['cpu_percent'] or 0.0,
                "memory_percent": round(info['memory_percent'] or 0.0, 2),
                "memory_mb": round(mem_mb, 2),
                "status": info['status']
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Sort by memory usage as proxy if cpu_percent isn't reliable instantaneously
    processes.sort(key=lambda x: x['memory_mb'], reverse=True)
    return processes[:50]

@app.delete("/processes/{pid}")
def kill_process(pid: int):
    try:
        proc = psutil.Process(pid)
        proc.kill()
        return {"success": True, "message": f"Process {pid} killed"}
    except psutil.NoSuchProcess:
        raise HTTPException(status_code=404, detail="Process not found")
    except psutil.AccessDenied:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_real_services():
    services = []
    for svc in MOCK_SERVICES:
        name = svc["name"]
        display_name = svc["display_name"]
        try:
            result = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True)
            status_output = result.stdout.strip()
            
            result_enabled = subprocess.run(["systemctl", "is-enabled", name], capture_output=True, text=True)
            enabled = result_enabled.stdout.strip() == "enabled"
            
            is_running = status_output == "active"
            
            services.append({
                "name": name,
                "display_name": display_name,
                "status": "running" if is_running else "stopped",
                "enabled": enabled
            })
        except Exception:
            services.append({
                "name": name,
                "display_name": display_name,
                "status": "stopped",
                "enabled": False
            })
    return services

@app.get("/services")
def get_services():
    if platform.system() == "Linux":
        return get_real_services()
    return MOCK_SERVICES

class ServiceAction(BaseModel):
    action: str

@app.post("/services/{name}/action")
def service_action(name: str, action: ServiceAction):
    if platform.system() == "Linux":
        if name not in [s["name"] for s in MOCK_SERVICES]:
            raise HTTPException(status_code=404, detail="Service not found")
        
        if action.action not in ["start", "stop", "restart"]:
            raise HTTPException(status_code=400, detail="Invalid action")
            
        try:
            # Attempt to use sudo for systemctl commands as they usually require root
            subprocess.run(["sudo", "systemctl", action.action, name], check=True)
            return {"success": True, "message": f"{name} {action.action}ed successfully"}
        except subprocess.CalledProcessError:
            raise HTTPException(status_code=500, detail=f"Failed to {action.action} service {name}")
    else:
        for svc in MOCK_SERVICES:
            if svc["name"] == name:
                if action.action == "start":
                    svc["status"] = "running"
                elif action.action == "stop":
                    svc["status"] = "stopped"
                elif action.action == "restart":
                    svc["status"] = "running"
                return {"success": True, "message": f"{name} {action.action}ed successfully"}
        
        raise HTTPException(status_code=404, detail="Service not found")
