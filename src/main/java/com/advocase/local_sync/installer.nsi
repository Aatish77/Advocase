!include "MUI2.nsh"
!include "FileFunc.nsh"

Name "S3 Drive Mount"
OutFile "S3DriveMountSetup.exe"
InstallDir "$PROGRAMFILES\S3DriveMount"

!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "MainSection" SEC01
    SetOutPath "$INSTDIR"
    
    ; Extract files
    File "dist\s3_drive_mount.exe"
    File "config.ini"
    
    ; Create startup entry (both current user and all users)
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "S3DriveMount" '"$INSTDIR\s3_drive_mount.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "S3DriveMount" '"$INSTDIR\s3_drive_mount.exe"'
    
    ; Create startup shortcut
    CreateDirectory "$SMSTARTUP"
    CreateShortCut "$SMSTARTUP\S3DriveMount.lnk" "$INSTDIR\s3_drive_mount.exe"
    
    ; Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    ; Create start menu shortcuts
    CreateDirectory "$SMPROGRAMS\S3DriveMount"
    CreateShortCut "$SMPROGRAMS\S3DriveMount\S3DriveMount.lnk" "$INSTDIR\s3_drive_mount.exe"
    CreateShortCut "$SMPROGRAMS\S3DriveMount\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    
    ; Launch application immediately after install
    ExecShell "" "$INSTDIR\s3_drive_mount.exe"
SectionEnd

Section "Uninstall"
    ; Remove startup entries
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "S3DriveMount"
    DeleteRegValue HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "S3DriveMount"
    Delete "$SMSTARTUP\S3DriveMount.lnk"
    
    ; Remove files
    Delete "$INSTDIR\s3_drive_mount.exe"
    Delete "$INSTDIR\config.ini"
    Delete "$INSTDIR\Uninstall.exe"
    
    ; Remove shortcuts
    Delete "$SMPROGRAMS\S3DriveMount\S3DriveMount.lnk"
    Delete "$SMPROGRAMS\S3DriveMount\Uninstall.lnk"
    RMDir "$SMPROGRAMS\S3DriveMount"
    
    ; Remove install directory
    RMDir "$INSTDIR"
SectionEnd