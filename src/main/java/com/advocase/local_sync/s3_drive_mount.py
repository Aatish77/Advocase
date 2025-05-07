import requests
import boto3
import s3fs
import os
import sys
from PIL import Image
import pystray
import configparser
from pathlib import Path
import subprocess
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tqdm import tqdm

class S3EventHandler(FileSystemEventHandler):
    def __init__(self, s3_client, bucket_name, root_folder):
        super().__init__()  # Initialize parent class
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.root_folder = root_folder  # Store root_folder as instance variable

    def on_modified(self, event):
        if not event.is_directory:
            rel_path = os.path.relpath(event.src_path, os.path.join(os.environ['USERPROFILE'], self.root_folder))
            try:
                self.s3_client.upload_file(event.src_path, self.bucket_name, rel_path)
                print(f"Uploaded {rel_path} to S3")
            except Exception as e:
                print(f"Error uploading {rel_path}: {e}")

    def on_deleted(self, event):
        rel_path = os.path.relpath(event.src_path, os.path.join(os.environ['USERPROFILE'],self.root_folder))
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
        self.sync_interval = 300  # default 30 seconds
        self.selected_folders = []
        self.get_folders_from_api() 
        self.observer = None

    def refresh_folders(self):
        """Refresh the selected folders from the API."""
        self.get_folders_from_api()
        print(f"Selected folders updated: {self.selected_folders}")

    def get_root_folder_from_api(self):
        # return "advocate1"
        return "ROOT_FOLDER_PLACEHOLDER"
        # try:
        #     api_url = "http://localhost:8080/api/root-folder"
        #     response = requests.get(api_url)
        #     if response.status_code == 200:
        #         root_folder = response.text.strip('"')
        #         print(f"Root folder received from API: {root_folder}")
        #         return root_folder
        #     else:
        #         print(f"Failed to get root folder from API. Status code: {response.status_code}")
        #         return "Advocase77"  # fallback root folder
        # except Exception as e:
        #     print(f"Error fetching root folder from API: {e}")
        #     return "Advocase77"  # fallback root folder    
    def get_folders_from_api(self):
        try:
            api_url = "http://192.168.31.7:8080/api/folders"
            response = requests.get(api_url)
            
            if response.status_code == 200:
                folders = response.json()
                self.selected_folders = folders
                print(f"Folders received from API: {folders}")
            else:
                print(f"Failed to get folders from API. Status code: {response.status_code}")
                self.selected_folders = []  # fallback folders
        except Exception as e:
            print(f"Error fetching folders from API: {e}")
            self.selected_folders = []

    def load_config(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        self.bucket_name = config['AWS']['bucket_name']
        self.mount_point = config['Drive']['mount_point']
        self.aws_access_key = config['AWS']['access_key']
        self.aws_secret_key = config['AWS']['secret_key']
        self.region = config['AWS']['region']
        self.sync_interval = int(config.get('Sync', 'interval', fallback=30))
        self.selected_folders = ['sample','sample2']
        print(f"Selected folders to syncing: {self.selected_folders}")

        # self.selected_folders = config.get('Sync', 'folders', fallback='').split(',')
        # self.selected_folders = [f.strip() for f in self.selected_folders if f.strip()]

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
        mount_path = os.path.join(os.environ['USERPROFILE'], root_folder)
        if not os.path.exists(mount_path):
            os.makedirs(mount_path)
        
        self.sync_s3_to_local(mount_path)
        self.setup_local_watcher(mount_path)
        self.start_sync_thread(mount_path)

    def unmount_drive(self):
        # Remove the fusermount command as we're not using FUSE anymore
        print("Stopping sync...")
        try:
            subprocess.run(['fusermount', '-u', self.mount_point], check=True)
        except Exception as e:
            print(f"Error unmounting drive: {e}")
        if self.observer:
            self.observer.stop()
            self.observer.join()

    def create_tray_icon(self):
        def sync_now(icon, item):
            root_folder = self.get_root_folder_from_api()
            mount_path = os.path.join(os.environ['USERPROFILE'], root_folder)
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

    def unmount_drive(self):
        print("Stopping sync...")
        root_folder = self.get_root_folder_from_api()
        mount_path = os.path.join(os.environ['USERPROFILE'], root_folder)
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

    def on_exit(self):
        self.unmount_drive()
        self.icon.stop()
        sys.exit(0)

    def run(self):
        self.mount_drive()
        self.create_tray_icon()
        # Periodically refresh folders
        threading.Thread(target=self.periodic_folder_refresh, daemon=True).start()
    def periodic_folder_refresh(self):
        """Periodically refresh folders from the API."""
        while True:
            self.refresh_folders()
            time.sleep(self.sync_interval)  # Refresh interval can be adjusted
    def sync_s3_to_local(self, local_path):
        try:
            print("\nStarting S3 to local sync...")
            # Fetch latest folders from API before syncing
            self.get_folders_from_api()
            
            root_folder = self.get_root_folder_from_api()
            print(f"Root folder to sync: {root_folder}")
            print(f"Selected folders to sync: {self.selected_folders}")
            
            # Remove unselected folders from local drive
            root_path = os.path.join(local_path, root_folder)
            if os.path.exists(root_path):
                for folder in os.listdir(root_path):
                    folder_path = os.path.join(root_path, folder)
                    if os.path.isdir(folder_path) and folder not in self.selected_folders:
                        print(f"Removing unselected folder: {folder}")
                        import shutil
                        shutil.rmtree(folder_path)
    
            s3_files = set()
            
            # Create base folder
            folder_path = os.path.join(local_path, root_folder)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                
            try:
                # List objects in the root folder for selected subfolders only
                paginator = self.s3_client.get_paginator('list_objects_v2')
                for folder in self.selected_folders:
                    folder_prefix = f"{root_folder}/{folder}/"
                    print(f"\nProcessing selected folder: {folder}")
                    
                    for page in paginator.paginate(Bucket=self.bucket_name, Prefix=folder_prefix):
                        if 'Contents' in page:
                            for obj in page['Contents']:
                                key = obj['Key']
                                if not key.endswith('/'):  # Skip folder markers
                                    print(f"Found file: {key}")
                                    s3_files.add(key)
                                    
                                    local_file_path = os.path.join(local_path, key)
                                    local_dir = os.path.dirname(local_file_path)
                                    
                                    # Create directory structure
                                    if not os.path.exists(local_dir):
                                        os.makedirs(local_dir)
                                        print(f"Created directory: {local_dir}")
                                    
                                    # Download file
                                    print(f"Downloading: {key}")
                                    self.s3_client.download_file(
                                        self.bucket_name,
                                        key,
                                        local_file_path
                                    )
                                    print(f"Downloaded: {key}")
                            
            except Exception as e:
                print(f"Error processing folders: {e}")
    
            # Get list of local files in selected folders
            local_files = set()
            for folder in self.selected_folders:
                folder_path = os.path.join(local_path, root_folder, folder)
                if os.path.exists(folder_path):
                    for root, _, files in os.walk(folder_path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, local_path).replace('\\', '/')
                            local_files.add(rel_path)
        
            # Delete local files that don't exist in S3
            files_to_delete = local_files - s3_files
            for file_to_delete in files_to_delete:
                local_file_path = os.path.join(local_path, file_to_delete)
                if os.path.exists(local_file_path):
                    try:
                        os.remove(local_file_path)
                        print(f"Deleted local file: {file_to_delete}")
                    except Exception as delete_error:
                        print(f"Error deleting local file {file_to_delete}: {delete_error}")
        
            # Clean up empty directories in selected folders
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
                time.sleep(self.sync_interval)  # Use configured sync interval
                
        sync_thread = threading.Thread(target=sync_periodically, daemon=True)
        sync_thread.start()

    def setup_local_watcher(self, local_path):
        root_folder = self.get_root_folder_from_api()
        event_handler = S3EventHandler(self.s3_client, self.bucket_name, root_folder)
        self.observer = Observer()
        self.observer.schedule(event_handler, local_path, recursive=True)
        self.observer.start()

    def _process_s3_prefix(self, prefix, local_path, s3_files):
        """Process a folder prefix and its contents"""
        print(f"Processing subfolder: {prefix}")
        
        # Create local subfolder
        local_subfolder = os.path.join(local_path, prefix.rstrip('/'))
        if not os.path.exists(local_subfolder):
            os.makedirs(local_subfolder)
        
        # List contents of this prefix
        response = self.s3_client.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix=prefix,
            Delimiter='/'
        )
        
        # Process files in this folder
        if 'Contents' in response:
            for obj in response['Contents']:
                self._process_s3_object(obj, local_path, s3_files)
        
        # Process nested subfolders
        if 'CommonPrefixes' in response:
            for nested_prefix in response['CommonPrefixes']:
                self._process_s3_prefix(nested_prefix['Prefix'], local_path, s3_files)

    def _process_s3_object(self, obj, local_path, s3_files):
        """Process individual S3 object"""
        key = obj['Key']
        if key.endswith('/'):  # Skip folder markers
            return
            
        print(f"Found file: {key}")
        s3_files.add(key)
        
        local_file_path = os.path.join(local_path, key)
        local_dir = os.path.dirname(local_file_path)
        
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
        
        print(f"Downloading: {key}")
        self.s3_client.download_file(
            self.bucket_name,
            key,
            local_file_path
        )
        print(f"Downloaded: {key}")

if __name__ == "__main__":
    app = S3DriveMount()
    app.run()