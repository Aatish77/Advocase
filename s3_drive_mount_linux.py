import requests
import boto3
import s3fs
import os
import sys
from pathlib import Path
import subprocess
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tqdm import tqdm

try:
    from PIL import Image
    import pystray
except ImportError:
    pystray = None  # Tray icon optional on Linux

class S3EventHandler(FileSystemEventHandler):
    def __init__(self, s3_client, bucket_name, root_folder):
        super().__init__()
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.root_folder = root_folder

    def on_modified(self, event):
        if not event.is_directory:
            rel_path = os.path.relpath(event.src_path, os.path.join(Path.home(), self.root_folder))
            try:
                self.s3_client.upload_file(event.src_path, self.bucket_name, rel_path)
                print(f"Uploaded {rel_path} to S3")
            except Exception as e:
                print(f"Error uploading {rel_path}: {e}")

    def on_deleted(self, event):
        rel_path = os.path.relpath(event.src_path, os.path.join(Path.home(), self.root_folder))
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=rel_path)
            print(f"Deleted {rel_path} from S3")
        except Exception as e:
            print(f"Error deleting {rel_path}: {e}")

class S3DriveMount:
    def __init__(self):
        self.s3_client = None
        self.s3fs = None
        self.bucket_name = None
        self.mount_point = None
        self.icon = None
        self.load_config()
        self.connect_s3()
        self.sync_interval = 300  # default 5 minutes
        self.selected_folders = []
        self.get_folders_from_api()
        self.observer = None

    def refresh_folders(self):
        self.get_folders_from_api()
        print(f"Selected folders updated: {self.selected_folders}")

    def get_root_folder_from_api(self):
        return "advocate3"
        # return "ROOT_FOLDER_PLACEHOLDER"
        # Uncomment and adjust if API is available
        # try:
        #     api_url = "http://localhost:8080/api/root-folder"
        #     response = requests.get(api_url)
        #     if response.status_code == 200:
        #         root_folder = response.text.strip('"')
        #         print(f"Root folder received from API: {root_folder}")
        #         return root_folder
        #     else:
        #         print(f"Failed to get root folder from API. Status code: {response.status_code}")
        #         return "Advocase77"
        # except Exception as e:
        #     print(f"Error fetching root folder from API: {e}")
        #     return "Advocase77"

    def get_folders_from_api(self):
        try:
            api_url = "http://localhost:8080/api/folders"
            response = requests.get(api_url)
            if response.status_code == 200:
                folders = response.json()
               
                self.selected_folders = folders
                print(f"Folders received from API: {folders}")
            else:
                print(f"Failed to get folders from API. Status code: {response.status_code}")
                self.selected_folders = []
        except Exception as e:
            print(f"Error fetching folders from API: {e}")
            self.selected_folders = []

    def load_config(self):
        import configparser
        config = configparser.ConfigParser()
        config.read('config.ini')

        self.bucket_name = config['AWS']['bucket_name']
        self.mount_point = config['Drive']['mount_point']
        self.aws_access_key = config['AWS']['access_key']
        self.aws_secret_key = config['AWS']['secret_key']
        self.region = config['AWS']['region']
        self.sync_interval = int(config.get('Sync', 'interval', fallback=300))
        self.selected_folders = ['sample', 'sample2']
        print(f"Selected folders to syncing: {self.selected_folders}")

    def connect_s3(self):
        self.s3fs = s3fs.S3FileSystem(
            key=self.aws_access_key,
            secret=self.aws_secret_key,
            client_kwargs={'region_name': self.region}
        )
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.region
        )

    def mount_drive(self):
        root_folder = self.get_root_folder_from_api()
        mount_path = os.path.join(Path.home(), root_folder)
        if not os.path.exists(mount_path):
            os.makedirs(mount_path)

        self.sync_s3_to_local(mount_path)
        self.setup_local_watcher(mount_path)
        self.start_sync_thread(mount_path)

    def unmount_drive(self):
        print("Stopping sync...")
        root_folder = self.get_root_folder_from_api()
        mount_path = os.path.join(Path.home(), root_folder)
        try:
            if os.path.exists(mount_path):
                import shutil
                shutil.rmtree(mount_path)
                print(f"Removed sync directory: {mount_path}")
        except Exception as e:
            print(f"Error cleaning up sync directory: {e}")
        if self.observer:
            self.observer.stop()
            self.observer.join()

    def create_tray_icon(self):
        if pystray is None:
            print("pystray not installed, tray icon disabled.")
            return

        def sync_now(icon, item):
            root_folder = self.get_root_folder_from_api()
            mount_path = os.path.join(Path.home(), root_folder)
            self.sync_s3_to_local(mount_path)

        image = Image.new('RGB', (64, 64), color='blue')
        self.icon = pystray.Icon(
            "S3Drive",
            image,
            "S3 Drive Mount",
            menu=pystray.Menu(
                pystray.MenuItem("Sync Now", sync_now),
                pystray.MenuItem("Exit", self.on_exit)
            )
        )
        self.icon.run()

    def on_exit(self):
        self.unmount_drive()
        if self.icon:
            self.icon.stop()
        sys.exit(0)

    def run(self):
        self.mount_drive()
        self.create_tray_icon()
        threading.Thread(target=self.periodic_folder_refresh, daemon=True).start()

    def periodic_folder_refresh(self):
        while True:
            self.refresh_folders()
            time.sleep(self.sync_interval)

    def sync_s3_to_local(self, local_path):
        try:
            print("\nStarting S3 to local sync...")
            self.get_folders_from_api()

            root_folder = self.get_root_folder_from_api()
            print(f"Root folder to sync: {root_folder}")
            print(f"Selected folders to sync: {self.selected_folders}")

            root_path = os.path.join(local_path, root_folder)
            if os.path.exists(root_path):
                for folder in os.listdir(root_path):
                    folder_path = os.path.join(root_path, folder)
                    if os.path.isdir(folder_path) and folder not in self.selected_folders:
                        print(f"Removing unselected folder: {folder}")
                        import shutil
                        shutil.rmtree(folder_path)

            s3_files = set()

            folder_path = os.path.join(local_path, root_folder)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

            paginator = self.s3_client.get_paginator('list_objects_v2')
            for folder in self.selected_folders:
                folder_prefix = f"{root_folder}/{folder}/"
                print(f"\nProcessing selected folder: {folder}")

                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=folder_prefix):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            key = obj['Key']
                            if not key.endswith('/'):
                                print(f"Found file: {key}")
                                s3_files.add(key)

                                local_file_path = os.path.join(local_path, key)
                                local_dir = os.path.dirname(local_file_path)

                                if not os.path.exists(local_dir):
                                    os.makedirs(local_dir)
                                    print(f"Created directory: {local_dir}")

                                print(f"Downloading: {key}")
                                self.s3_client.download_file(
                                    self.bucket_name,
                                    key,
                                    local_file_path
                                )
                                print(f"Downloaded: {key}")

            local_files = set()
            for folder in self.selected_folders:
                folder_path = os.path.join(local_path, root_folder, folder)
                if os.path.exists(folder_path):
                    for root, _, files in os.walk(folder_path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, local_path).replace('\\', '/')
                            local_files.add(rel_path)

            files_to_delete = local_files - s3_files
            for file_to_delete in files_to_delete:
                local_file_path = os.path.join(local_path, file_to_delete)
                if os.path.exists(local_file_path):
                    try:
                        os.remove(local_file_path)
                        print(f"Deleted local file: {file_to_delete}")
                    except Exception as delete_error:
                        print(f"Error deleting local file {file_to_delete}: {delete_error}")

            for folder in self.selected_folders:
                folder_path = os.path.join(local_path, root_folder, folder)
                if os.path.exists(folder_path):
                    for root, dirs, files in os.walk(folder_path, topdown=False):
                        for dir_name in dirs:
                            dir_path = os.path.join(root, dir_name)
                            if not os.listdir(dir_path):
                                os.rmdir(dir_path)
                                print(f"Removed empty directory: {dir_path}")

            print(f"\nSync completed. Files synced: {len(s3_files)}, Files deleted: {len(files_to_delete)}")

        except Exception as e:
            print(f"\nError during sync: {str(e)}")
            print(f"Error type: {type(e).__name__}")

    def start_sync_thread(self, local_path):
        def sync_periodically():
            while True:
                self.sync_s3_to_local(local_path)
                time.sleep(self.sync_interval)

        sync_thread = threading.Thread(target=sync_periodically, daemon=True)
        sync_thread.start()

    def setup_local_watcher(self, local_path):
        root_folder = self.get_root_folder_from_api()
        event_handler = S3EventHandler(self.s3_client, self.bucket_name, root_folder)
        self.observer = Observer()
        self.observer.schedule(event_handler, local_path, recursive=True)
        self.observer.start()

if __name__ == "__main__":
    app = S3DriveMount()
    app.run()
