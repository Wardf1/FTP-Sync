import os
import logging
from pathlib import Path

# Konfiguracja
FOLDER_PATH = "download_folder_path"  # Zmień na właściwą ścieżkę
LIMIT_TB = 1  # Limit w TB
LOG_FILE = "Log_path_with_filename"  # Gdzie logować operacje

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
    limit_bytes = LIMIT_TB * 1024**4  # Konwersja TB na bajty

    logging.info(f"Sprawdzam folder {FOLDER_PATH}: {folder_size / 1024**4:.2f} TB")

    if folder_size > limit_bytes:
        oldest_file = get_oldest_file(FOLDER_PATH)
        if oldest_file:
            try:
                os.remove(oldest_file)
                logging.info(f"Usunięto plik: {oldest_file} ({oldest_file.stat().st_size / 1024**3:.2f} GB)")
            except Exception as e:
                logging.error(f"Błąd podczas usuwania {oldest_file}: {e}")
        else:
            logging.warning("Nie znaleziono plików do usunięcia.")
    else:
        logging.info("Folder nie przekracza limitu, czyszczenie nie jest wymagane.")

if __name__ == "__main__":
    cleanup_folder()
