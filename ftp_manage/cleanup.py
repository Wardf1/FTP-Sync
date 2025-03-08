import os
import logging
from pathlib import Path

# Konfiguracja
FOLDER_PATH = "folder_backup"  # Zmień na właściwą ścieżkę
LIMIT_GB = 1000  # Limit w GB
LOG_FILE = "folder_logger"  # Gdzie logować operacje

# Konfiguracja loggera
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def get_folder_size_bytes(folder):
    """Zwraca rozmiar folderu w bajtach."""
    return sum(f.stat().st_size for f in Path(folder).rglob('*') if f.is_file())

def get_oldest_file(folder):
    """Zwraca najstarszy plik w folderze."""
    files = sorted(
        (f for f in Path(folder).rglob('*') if f.is_file()),
        key=lambda f: f.stat().st_mtime
    )
    return files[0] if files else None

def cleanup_folder():
    """Sprawdza rozmiar folderu i usuwa najstarszy plik, jeśli przekracza limit."""
    folder_size = get_folder_size_bytes(FOLDER_PATH)
    limit_bytes = LIMIT_GB * 1024**3  # Konwersja GB na bajty

    logging.info(f"Sprawdzam folder {FOLDER_PATH}: {folder_size / 1024**3:.2f} GB")

    if folder_size > limit_bytes:
        oldest_file = get_oldest_file(FOLDER_PATH)
        
        if oldest_file:
            file_size = oldest_file.stat().st_size / 1024**3  # Pobranie rozmiaru przed usunięciem
            logging.info(f"Najstarszy plik: {oldest_file} (istnieje: {oldest_file.exists()}), rozmiar: {file_size:.2f} GB")
            
            try:
                logging.info(f"Usunięto plik: {oldest_file} ({file_size:.2f} GB)")
                os.remove(oldest_file)
            except FileNotFoundError:
                logging.warning(f"Plik {oldest_file} został usunięty przed próbą usunięcia przez skrypt.")
            except Exception as e:
                logging.error(f"Błąd podczas usuwania {oldest_file}: {e}")
        else:
            logging.warning("Brak plików do usunięcia!")
    else:
        logging.info("Folder nie przekracza limitu, czyszczenie nie jest wymagane.")

if __name__ == "__main__":
    cleanup_folder()
