import ftplib
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Wczytanie zmiennych z pliku .env
load_dotenv()

# Konfiguracja serwera FTP
FTP_HOST = os.getenv("FTP_HOST")
FTP_PORT = int(os.getenv("FTP_PORT", 21))
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
REMOTE_DIR = os.getenv("REMOTE_DIR")
LOCAL_DIR = os.getenv("LOCAL_DIR")

# Konfiguracja logowania
LOG_FILE = os.path.join(LOCAL_DIR, "ftp_sync.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def connect_ftp():
    """Łączy się z serwerem FTP i przechodzi do katalogu."""
    try:
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        print(f"REMOTE_DIR = {REMOTE_DIR}")
        ftp.cwd(REMOTE_DIR)
        logging.info("Połączono z FTP: %s i przełączono do katalogu %s", FTP_HOST, REMOTE_DIR)
        files = ftp.nlst()
        logging.info("Pliki w katalogu backup: %s", files)
        return ftp
    except Exception as e:
        logging.error("Błąd połączenia z FTP lub przejscia do katalogu backup: %s", str(e))
        return None

def list_remote_files(ftp):
    """Zwraca listę plików w katalogu FTP z datami modyfikacji."""
    try:
        files = ftp.nlst()
        files = [f for f in files if "." in f]  # Filtrujemy katalogi
        if not files:
            logging.warning("Brak plików w katalogu FTP.")
            return []

        file_dates = {}
        for file in files:
            try:
                modified_time = ftp.sendcmd(f"MDTM {file}")[4:].strip()
                file_dates[file] = datetime.strptime(modified_time, "%Y%m%d%H%M%S")
            except Exception as e:
                logging.warning("Nie udało się pobrać daty dla %s: %s", file, str(e))

        return sorted(file_dates.items(), key=lambda x: x[1])  # Sortowanie wg daty
    except Exception as e:
        logging.error("Błąd pobierania listy plików: %s", str(e))
        return []

def download_file(ftp, filename):
    """Pobiera pojedynczy plik z FTP, jeśli nie istnieje w lokalnym katalogu."""
    local_path = os.path.join(LOCAL_DIR, filename)
    if os.path.exists(local_path):
        logging.info("Plik %s już istnieje, pomijam pobieranie.", filename)
        return

    try:
        with open(local_path, "wb") as f:
            logging.info("Rozpoczęcie pobierania pliku: %s", filename)
            start_time = datetime.now()

            def progress(block):
                """Zapisuje blok pliku i loguje jego pobranie."""
                f.write(block)

            ftp.retrbinary(f"RETR {filename}", progress)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logging.info("Zakończono pobieranie pliku: %s (Czas: %.2f sek.)", filename, duration)

    except Exception as e:
        logging.error("Błąd podczas pobierania pliku %s: %s", filename, str(e))

def download_all_files(ftp, files):
    """Pobiera całą zawartość katalogu FTP."""
    for filename, _ in files:
        download_file(ftp, filename)

def delete_oldest_file(ftp, files):
    """Usuwa najstarszy plik z serwera FTP, jeśli jest więcej niż 1 plik."""
    if len(files) <= 1:
        logging.info("W katalogu jest tylko 1 plik, nie usuwam nic.")
        return

    oldest_file = files[0][0]  # Najstarszy plik (pierwszy w posortowanej liście)
    try:
        ftp.delete(oldest_file)
        logging.info("Usunięto najstarszy plik z FTP: %s", oldest_file)
    except Exception as e:
        logging.error("Błąd podczas usuwania pliku %s: %s", oldest_file, str(e))

def main():
    logging.info("=== Rozpoczęcie synchronizacji FTP ===")
    ftp = connect_ftp()
    if ftp:
        files = list_remote_files(ftp)
        if not files:
            logging.info("Brak plików na serwerze, kończę działanie.")
            ftp.quit()
            return

        # Jeśli na serwerze jest tylko jeden plik
        if len(files) == 1:
            single_file = files[0][0]
            local_files = os.listdir(LOCAL_DIR)

            # Sprawdzamy, czy ten plik już istnieje lokalnie
            if single_file not in local_files:
                logging.info("Na FTP jest tylko 1 plik (%s) i nie ma go lokalnie – pobieram całą zawartość.", single_file)
                download_all_files(ftp, files)
            else:
                logging.info("Na FTP jest tylko 1 plik (%s), ale istnieje już lokalnie – nie pobieram.", single_file)
        else:
            # Pobieramy najnowszy plik i usuwamy najstarszy
            latest_file = files[-1][0]  # Ostatni w posortowanej liście
            logging.info("Pobieram najnowszy plik: %s", latest_file)
            download_file(ftp, latest_file)

            delete_oldest_file(ftp, files)

        ftp.quit()
        logging.info("Połączenie FTP zakończone.")
    logging.info("=== Zakończenie synchronizacji FTP ===\n")

if __name__ == "__main__":
    main()
