import discord
import asyncio
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Wczytanie konfiguracji z .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# Folder monitorowany
FOLDER_TO_WATCH = "download_folder_path"

# Pliki logów
FTP_SYNC_LOG = os.path.join(FOLDER_TO_WATCH, "ftp_sync.log")
FOLDER_CLEANUP_LOG = os.path.join(FOLDER_TO_WATCH, "folder_cleanup.log")
LOG_FILES = {
    "ftp_sync": FTP_SYNC_LOG,
    "folder_cleanup": FOLDER_CLEANUP_LOG
}

# Ustawienia Discorda
intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

def read_last_sync_logs():
    if not os.path.exists(FTP_SYNC_LOG):
        return ["⚠️ Brak pliku logów synchronizacji FTP."]

    with open(FTP_SYNC_LOG, "r") as file:
        logs = file.readlines()

    sessions = []
    current_session = []
    in_sync_session = False

    for line in logs:
        if "INFO - === Rozpoczęcie synchronizacji FTP ===" in line:
            in_sync_session = True
            current_session = [line]
        elif in_sync_session:
            current_session.append(line)
        if "INFO - === Zakończenie synchronizacji FTP ===" in line:
            sessions.append(current_session)
            in_sync_session = False

    return sessions[-1] if sessions else ["⚠️ Nie znaleziono zakończonej sesji synchronizacji FTP."]

class LogMonitor(FileSystemEventHandler):
    def __init__(self, channel):
        self.channel = channel
        self.file_positions = {log: self.get_file_size(log) for log in LOG_FILES.values()}

    def get_file_size(self, file_path):
        return os.path.getsize(file_path) if os.path.exists(file_path) else 0

    async def send_message(self, message):
        await self.channel.send(message)

    def on_modified(self, event):
        if event.src_path in LOG_FILES.values():
            asyncio.run_coroutine_threadsafe(self.process_log_update(event.src_path), client.loop)

    async def process_log_update(self, file_path):
        previous_position = self.file_positions.get(file_path, 0)
        if not os.path.exists(file_path):
            return
        
        current_size = os.path.getsize(file_path)
        if current_size > previous_position:
            with open(file_path, "r") as file:
                file.seek(previous_position)
                new_lines = file.readlines()
                self.file_positions[file_path] = current_size
                
                if new_lines:
                    if file_path == FTP_SYNC_LOG and any("INFO - === Zakończenie synchronizacji FTP ===" in line for line in new_lines):
                        await send_last_sync_session(self.channel)
                    else:
                        log_name = "ftp_sync" if file_path == FTP_SYNC_LOG else "folder_cleanup"
                        await self.send_message(f"📜 **Nowe logi z `{log_name}`:**\n```" + "".join(new_lines) + "```")

async def send_last_sync_session(channel):
    sync_logs = read_last_sync_logs()
    if sync_logs:
        full_message = "📜 **Ostatnia zakończona synchronizacja FTP:**\n" + "".join(sync_logs)
        await channel.send(f"```{full_message}```")
    await send_file_list(channel)

async def send_file_list(channel):
    if not os.path.exists(FOLDER_TO_WATCH):
        await channel.send(f"❌ Folder `{FOLDER_TO_WATCH}` nie istnieje.")
        return
    
    files = [f for f in os.listdir(FOLDER_TO_WATCH) if not f.endswith(".log")]
    if files:
        message = "📂 **Lista plików w folderze `backups`:**\n"
        for file in files:
            file_path = os.path.join(FOLDER_TO_WATCH, file)
            file_size = os.path.getsize(file_path) / (1024 ** 3) if os.path.exists(file_path) else 0
            message += f"- {file} ({file_size:.2f} GB)\n"
    else:
        message = "📂 Folder jest pusty."
    await channel.send(message)

async def send_last_logs(channel):
    await send_last_sync_session(channel)
    for log_name, log_path in LOG_FILES.items():
        if os.path.exists(log_path) and log_path != FTP_SYNC_LOG:
            with open(log_path, "r") as file:
                last_lines = file.readlines()[-5:]
                if last_lines:
                    await channel.send(f"📜 **Ostatnie logi z `{log_name}`:**\n```" + "".join(last_lines) + "```")

@client.event
async def on_ready():
    print(f'✅ Zalogowano jako {client.user}')
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("📡 Bot monitoruje logi i folder `backups`.")
        await send_file_list(channel)
        await send_last_logs(channel)
    
    event_handler = LogMonitor(channel)
    observer = Observer()
    observer.schedule(event_handler, FOLDER_TO_WATCH, recursive=False)
    observer.start()

client.run(TOKEN)
