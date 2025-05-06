package com.advocase.local_sync;

import org.springframework.http.ResponseEntity;

// package com.advocase.localsync.controller;

import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Arrays;

//linux
import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveOutputStream;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import java.io.*;
import java.nio.file.*;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "*")
public class FolderController {

    @GetMapping("/folders")
    public List<String> getFolders() {
        // Replace this with your actual folder list or database query
        return Arrays.asList("case3");
    }

    @PostMapping("/folders")
    public List<String> updateFolders(@RequestBody List<String> folders) {
        // Here you can add logic to save folders to database
        return folders;
    }

    @GetMapping("/root-folder")
    public String getRootFolder() {
        return "advocate1";  // Replace with your actual root folder logic
    }

    @PostMapping("/create-exe")
    public ResponseEntity<org.springframework.core.io.Resource> createExe(@RequestParam String advocateId) {
        try {
            String exePath;
            // Generate Python executable
            try {
                exePath = generatePythonExecutable(advocateId);
                System.out.println("Executable generated at: " + exePath);

            } catch (java.io.IOException | InterruptedException e) {
                System.err.println("Failed to generate Python executable: " + e.getMessage());
                return ResponseEntity.status(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR).build();
            }

            // Package into ZIP
            String zipPath = packageIntoZip(exePath);

            try {
                zipPath = packageIntoZip(exePath);
                System.out.println("ZIP file created at: " + zipPath);
            } catch (java.io.IOException e) {
                System.err.println("Failed to package into ZIP: " + e.getMessage());
                return ResponseEntity.status(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR).build();
            }
            // Return ZIP file as response
        org.springframework.core.io.FileSystemResource resource = new org.springframework.core.io.FileSystemResource(zipPath);
        return ResponseEntity.ok()
                .header("Content-Disposition", "attachment; filename=\"installation.zip\"")
                .contentType(org.springframework.http.MediaType.APPLICATION_OCTET_STREAM)
                .body(resource);
        } catch (Exception e) {
            System.err.println("Unexpected error: " + e.getMessage());
            return ResponseEntity.status(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    private String generatePythonExecutable(String advocateId) throws java.io.IOException, InterruptedException {
        
        // Path to the Python script
        String pythonScriptPath = "s3_drive_mount.py";
        // String pythonScriptPath = "c:\\Advocase Cloud Delete Functionality Exe\\Advocase cloud org\\s3_drive_mount.py";
    
        // Modify the Python script to use advocateId as the root folder
        // You can use a placeholder in the script and replace it with advocateId
        java.nio.file.Path tempScriptPath = java.nio.file.Files.createTempFile("s3_drive_mount", ".py");
        List<String> lines = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(pythonScriptPath));
        List<String> modifiedLines = lines.stream()
            .map(line -> line.replace("ROOT_FOLDER_PLACEHOLDER", advocateId))
            .collect(java.util.stream.Collectors.toList());
            java.nio.file.Files.write(tempScriptPath, modifiedLines);
    
        // Use PyInstaller to generate the executable
        ProcessBuilder processBuilder = new ProcessBuilder(
            "pyinstaller",
            "--onefile",
            "--name", 
            "s3_drive_mount",  // Specify the name of the executable
            "--distpath",
            "dist",
            // "c:\\Advocase Cloud Delete Functionality Exe\\Advocase cloud org\\dist",
            tempScriptPath.toString()
        );
        processBuilder.inheritIO();
        Process process = processBuilder.start();
        process.waitFor();
    
        // Return the path to the generated executable
        return "dist\\s3_drive_mount.exe";
    }

    public String packageIntoZip(String exePath) throws java.io.IOException {
        
        // Create installer first
        try {
            String nsisPath = "C:\\Program Files (x86)\\NSIS\\makensis.exe";
            // Check if NSIS exists
            if (!new java.io.File(nsisPath).exists()) {
                System.err.println("NSIS not found. Skipping installer creation.");
            } else {
                ProcessBuilder processBuilder = new ProcessBuilder(
                    nsisPath,
                    "installer.nsi"
                );
                processBuilder.inheritIO();
                Process process = processBuilder.start();
                process.waitFor();
            }
        } catch (InterruptedException e) {
            throw new java.io.IOException("Failed to create installer", e);
        }
        // Path to the ZIP file
        String zipFilePath = "installation.zip";
        String installerPath = "S3DriveMountSetup.exe";
        // Path to the config.ini file
        String configFilePath = "config.ini";
        // Create a ZIP file
        try (java.util.zip.ZipOutputStream zos = new java.util.zip.ZipOutputStream(new java.io.FileOutputStream(zipFilePath))) {
            // Add the installer to the ZIP instead of the raw exe
            java.io.File installerFile = new java.io.File(installerPath);
            try (java.io.FileInputStream fis = new java.io.FileInputStream(installerFile)) {
                java.util.zip.ZipEntry zipEntry = new java.util.zip.ZipEntry(installerFile.getName());
                zos.putNextEntry(zipEntry);
    
                byte[] buffer = new byte[1024];
                int length;
                while ((length = fis.read(buffer)) > 0) {
                    zos.write(buffer, 0, length);
                }
            }
            zos.closeEntry();
            // Add readme file with installation instructions
        String readmeContent = "1. Run S3DriveMountSetup.exe\n2. Follow the installation wizard\n3. The application will start automatically after installation and on system startup";
        zos.putNextEntry(new java.util.zip.ZipEntry("README.txt"));
        zos.write(readmeContent.getBytes());
        zos.closeEntry();
               // Add the config.ini file to the ZIP
        java.io.File configFile = new java.io.File(configFilePath);
        try (java.io.FileInputStream fis = new java.io.FileInputStream(configFile)) {
            java.util.zip.ZipEntry zipEntry = new java.util.zip.ZipEntry(configFile.getName());
            zos.putNextEntry(zipEntry);

            byte[] buffer = new byte[1024];
            int length;
            while ((length = fis.read(buffer)) > 0) {
                zos.write(buffer, 0, length);
            }
        }
        zos.closeEntry();
    
        }
    
        // Return the path to the ZIP file
        return zipFilePath;
    }

    @PostMapping("/create-linux-installer")
public ResponseEntity<Resource> createLinuxInstaller(@RequestParam String advocateId) {
    try {
        // Create temporary directory for files
        Path tempDir = Files.createTempDirectory("linux-installer");
        
        // Generate install script
        String installScript = generateInstallScript();
        Files.write(tempDir.resolve("install.sh"), installScript.getBytes());
        
        // Generate README
        String readme = generateReadme();
        Files.write(tempDir.resolve("README.md"), readme.getBytes());
        
        // Copy and modify Python script
        String pythonScript = modifyPythonScript(advocateId);
        Files.write(tempDir.resolve("s3_drive_mount.py"), pythonScript.getBytes());
        
        // Copy config file
        Files.copy(Paths.get("config.ini"), 
                  tempDir.resolve("config.ini"));
        
        // Create tar file
        String tarPath = "installation.tar";
        createTarFile(tempDir, tarPath);
        
        // Return tar file as response
        Resource resource = new FileSystemResource(tarPath);
        return ResponseEntity.ok()
                .header("Content-Disposition", "attachment; filename=\"installation.tar\"")
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .body(resource);
                
    } catch (Exception e) {
        e.printStackTrace();
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
    }
}

private String generateInstallScript() {
    return "#!/bin/bash\n\n" +
           "# Installation directory\n" +
           "INSTALL_DIR=\"/opt/s3drivemount\"\n" +
           "CONFIG_DIR=\"$HOME/.config/s3drivemount\"\n" +
           "SERVICE_FILE=\"/etc/systemd/system/s3drivemount.service\"\n\n" +
           "# Create directories\n" +
           "sudo mkdir -p \"$INSTALL_DIR\"\n" +
           "mkdir -p \"$CONFIG_DIR\"\n\n" +
           "# Copy files\n" +
           "sudo cp s3_drive_mount.py \"$INSTALL_DIR/\"\n" +
           "cp config.ini \"$CONFIG_DIR/\"\n\n" +
           "# Create systemd service file\n" +
           "cat << EOF | sudo tee \"$SERVICE_FILE\"\n" +
           "[Unit]\n" +
           "Description=S3 Drive Mount Service\n" +
           "After=network.target\n\n" +
           "[Service]\n" +
           "Type=simple\n" +
           "User=$USER\n" +
           "ExecStart=/usr/bin/python3 $INSTALL_DIR/s3_drive_mount.py\n" +
           "Restart=always\n" +
           "Environment=PYTHONUNBUFFERED=1\n\n" +
           "[Install]\n" +
           "WantedBy=multi-user.target\n" +
           "EOF\n\n" +
           "# Install dependencies\n" +
           "sudo apt-get update\n" +
           "sudo apt-get install -y python3 python3-pip\n" +
           "pip3 install boto3 s3fs pillow pystray watchdog tqdm requests\n\n" +
           "# Set permissions\n" +
           "sudo chmod +x \"$INSTALL_DIR/s3_drive_mount.py\"\n" +
           "sudo chmod 644 \"$SERVICE_FILE\"\n\n" +
           "# Enable and start service\n" +
           "sudo systemctl daemon-reload\n" +
           "sudo systemctl enable s3drivemount\n" +
           "sudo systemctl start s3drivemount\n\n" +
           "echo \"Installation completed successfully!\"\n";
}

private String generateReadme() {
    return "# S3 Drive Mount\n\n" +
           "## Installation\n\n" +
           "1. Extract the tar file\n" +
           "2. Make the installer executable:\n" +
           "   ```bash\n" +
           "   chmod +x install.sh\n" +
           "   ```\n" +
           "3. Run the installer:\n" +
           "   ```bash\n" +
           "   ./install.sh\n" +
           "   ```\n\n" +
           "## Usage\n\n" +
           "The application will start automatically on system boot.\n" +
           "You can control it using:\n\n" +
           "```bash\n" +
           "sudo systemctl start s3drivemount\n" +
           "sudo systemctl stop s3drivemount\n" +
           "sudo systemctl status s3drivemount\n" +
           "```\n";
}

private String modifyPythonScript(String advocateId) throws IOException {
    Path pythonScriptPath = Paths.get("s3_drive_mount.py");
    List<String> lines = Files.readAllLines(pythonScriptPath);
    return lines.stream()
            .map(line -> line.replace("ROOT_FOLDER_PLACEHOLDER", advocateId))
            .collect(Collectors.joining("\n"));
}

private void createTarFile(Path sourceDir, String tarPath) throws IOException {
    try (TarArchiveOutputStream tarOs = new TarArchiveOutputStream(
            new BufferedOutputStream(new FileOutputStream(tarPath)))) {
        Files.walk(sourceDir)
                .filter(path -> !Files.isDirectory(path))
                .forEach(path -> {
                    try {
                        TarArchiveEntry entry = new TarArchiveEntry(
                                path.toFile(), 
                                sourceDir.relativize(path).toString());
                        tarOs.putArchiveEntry(entry);
                        Files.copy(path, tarOs);
                        tarOs.closeArchiveEntry();
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                });
    }
}
}