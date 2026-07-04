; Inno Setup script for AetherLab.
; Compile after PyInstaller has produced dist/aetherlab (see build.py):
;   iscc packaging\installer.iss

#define MyAppName "AetherLab"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppExeName "aetherlab.exe"

[Setup]
AppId={{7A3E1F7E-32B1-4A76-9C29-AETHERLAB01}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=AetherLab
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputBaseFilename=AetherLab-Setup-{#MyAppVersion}
OutputDir=..\dist
SetupIconFile=..\assets\aetherlab.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\aetherlab\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

; Per-user data (settings, cache, library, logs) lives in %LOCALAPPDATA%\AetherLab
; and intentionally survives uninstall (textbooks are large downloads).
