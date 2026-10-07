#define MyAppName "FrenchNotes"
#define MyAppVersion "0.1.2"

[Setup]
; Keep this ID unchanged so later versions upgrade the same application.
AppId={{0D1280D3-6E15-4F02-ACBE-7D324964F42C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=FrenchNotes
AppPublisherURL=https://github.com/404-love-found/french-notes-windows
AppSupportURL=https://github.com/404-love-found/french-notes-windows/issues
AppUpdatesURL=https://github.com/404-love-found/french-notes-windows/releases
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=FrenchNotes-Setup-{#MyAppVersion}
VersionInfoVersion=0.1.2.0
VersionInfoProductVersion={#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\FrenchNotes.exe
CloseApplications=yes
RestartApplications=no
; No certificate is configured. The EXE, setup and uninstaller are unsigned.
SignedUninstaller=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\FrenchNotes.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README-windows.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FrenchNotes"; Filename: "{app}\FrenchNotes.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\FrenchNotes"; Filename: "{app}\FrenchNotes.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\FrenchNotes.exe"; Description: "{cm:LaunchProgram,FrenchNotes}"; Flags: nowait postinstall skipifsilent

; Notes/settings/backups live in {localappdata}\FrenchNotes, outside {app}.
; Do not add an [UninstallDelete] section for that data directory.
