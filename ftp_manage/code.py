import ftplib
import os
import logging
import subprocess
import time
from datetime import datetime
from dotenv import load_dotenv
import psutil
from tqdm import tqdm
import threading

# Wczytanie zmiennych z pliku .env
load_dotenv()

# Konfiguracja
FTP_HOST = os.getenv("FTP_HOST")
FTP_PORT = int(os.getenv("FTP_PORT", 21))
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
REMOTE_DIR = os.getenv("REMOTE_DIR")
LOCAL_DIR = os.getenv("LOCAL_DIR")
OVPN_CONFIG = os.getenv("OVPN_CONFIG")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

if not OVPN_CONFIG or not os.path.exists(OVPN_CONFIG):
    raise ValueError(f"Ścieżka do pliku .ovpn jest nieprawidłowa lub nie istnieje: {OVPN_CONFIG}")

LOG_FILE = os.path.join(LOCAL_DIR, "ftp_sync.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def log_info(msg):
    print(msg, flush=True)
    logging.info(msg)

def has_active_tun():
    return any(name.startswith("tun") for name in psutil.net_if_addrs())

def wait_for_tun(timeout=60):
    log_info("Czekam na interfejs VPN (tun*)...")
    for _ in range(timeout):
        if has_active_tun():
            log_info("Tunel VPN gotowy.")
            return True
        time.sleep(1)
    log_info("Timeout: brak interfejsu tun* po 60 sekundach.")
    return False

def start_vpn():
    try:
        log_info("Uruchamianie OpenVPN...")
        stdout_dest = None if DEBUG else subprocess.DEVNULL
        stderr_dest = None if DEBUG else subprocess.DEVNULL
        process = subprocess.Popen(
            ["sudo", "openvpn", "--config", OVPN_CONFIG],
            stdout=stdout_dest,
            stderr=stderr_dest
        )
        if not wait_for_tun():
            log_info("Tunel VPN nie został wykryty w czasie.")
            return None
        log_info("VPN uruchomiony.")
        return process
    except Exception as e:
        log_info(f"Błąd przy uruchamianiu VPN: {e}")
        return None

def stop_vpn(process):
    try:
        log_info("Zatrzymywanie OpenVPN...")
        process.terminate()
        process.wait()
        log_info("VPN zatrzymany.")
    except Exception as e:
        log_info(f"Błąd przy zatrzymywaniu VPN: {e}")

def connect_ftp():
    try:
        log_info(f"Łączenie z FTP: {FTP_HOST}:{FTP_PORT}...")
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(REMOTE_DIR)
        log_info("Połączono z FTP.")
        return ftp
    except Exception as e:
        log_info(f"Błąd połączenia z FTP: {e}")
        return None

def list_remote_files(ftp):
    try:
        log_info("Pobieranie listy plików z FTP...")
        files = ftp.nlst()
        files = [f for f in files if "." in f]
        file_dates = {}
        for file in files:
            try:
                modified_time = ftp.sendcmd(f"MDTM {file}")[4:].strip()
                file_dates[file] = datetime.strptime(modified_time, "%Y%m%d%H%M%S")
            except Exception as e:
                msg = f"Nie udało się pobrać daty dla {file}: {e}"
                print("Ostrzeżenie:", msg, flush=True)
                logging.warning(msg)
        sorted_files = sorted(file_dates.items(), key=lambda x: x[1])
        log_info(f"Znaleziono {len(sorted_files)} plików.")
        return sorted_files
    except Exception as e:
        log_info(f"Błąd listowania plików: {e}")
        return []

def keep_alive(ftp, stop_event):
    while not stop_event.is_set():
        try:
            ftp.voidcmd("NOOP")
        except Exception as e:
            log_info(f"Błąd podczas wysyłania NOOP: {e}")
            break
        stop_event.wait(60)

def download_file(ftp, filename):
    local_path = os.path.join(LOCAL_DIR, filename)
    try:
        log_info(f"Pobieranie pliku: {filename}...")
        ftp.sendcmd("TYPE I")
        size = ftp.size(filename)
        downloaded = 0
        mode = "wb"
        rest = None

        if os.path.exists(local_path):
            downloaded = os.path.getsize(local_path)
            if downloaded < size:
                log_info(f"Wznawianie od bajtu {downloaded}")
                mode = "ab"
                rest = downloaded
            elif downloaded == size:
                log_info("Plik już w pełni pobrany. Pomijam.")
                return
            else:
                log_info("Lokalny plik większy niż na FTP — nadpisuję.")
                mode = "wb"

        stop_event = threading.Event()
        noop_thread = threading.Thread(target=keep_alive, args=(ftp, stop_event))
        noop_thread.start()

        with open(local_path, mode) as f:
            pbar = tqdm(total=size, initial=downloaded, unit='B', unit_scale=True, desc=filename)

            def callback(data):
                f.write(data)
                pbar.update(len(data))

            start_time = time.time()
            ftp.retrbinary(f"RETR {filename}", callback, rest=rest)
            elapsed = time.time() - start_time
            pbar.close()

        stop_event.set()
        noop_thread.join()

        log_info(f"Pobrano plik: {filename} w {elapsed:.2f} sekundy.")
    except Exception as e:
        log_info(f"Błąd pobierania {filename}: {e}")

def main():
    log_info("=== Start synchronizacji FTP przez OpenVPN ===")
    vpn_process = start_vpn()
    if not vpn_process:
        log_info("Nie udało się uruchomić VPN. Przerywam.")
        return

    ftp = connect_ftp()
    if ftp:
        files = list_remote_files(ftp)
        if files:
            newest_file = files[-1][0]
            log_info(f"Pobieranie najnowszego pliku: {newest_file}")
            download_file(ftp, newest_file)
        else:
            log_info("Brak plików na serwerze FTP.")

        try:
            ftp.quit()
        except Exception as e:
            log_info(f"Błąd podczas zamykania połączenia FTP: {e}")

    stop_vpn(vpn_process)
    log_info("=== Koniec synchronizacji FTP ===")

if __name__ == "__main__":
    main()
