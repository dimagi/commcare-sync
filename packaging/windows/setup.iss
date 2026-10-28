; Inno Setup script for the Windows pilot installer.
;
;   ISCC.exe /DAppVersion=<version> packaging\windows\setup.iss
;
; Installs for the current user without administrator rights, adds a
; Start Menu shortcut and an uninstaller, and never touches the data
; directory (%LOCALAPPDATA%\commcare-sync), which the uninstaller leaves
; in place. No WebView2 bootstrapper: Windows 10 and 11 ship WebView2,
; and the launcher falls back to the browser without it. Unsigned.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7D3C4D7E-6B4A-4B6E-9D0B-2C3F5A8E1B61}
AppName=CommCare Data Pipeline
AppVersion={#AppVersion}
AppPublisher=Dimagi
AppPublisherURL=https://www.dimagi.com/
DefaultDirName={autopf}\CommCare Data Pipeline
DefaultGroupName=CommCare Data Pipeline
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\commcare-sync.exe
OutputDir=..\..\dist
OutputBaseFilename=CommCare-Data-Pipeline-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\..\dist\commcare-sync\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CommCare Data Pipeline"; Filename: "{app}\commcare-sync.exe"
Name: "{group}\Uninstall CommCare Data Pipeline"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\commcare-sync.exe"; Description: "Start CommCare Data Pipeline"; Flags: nowait postinstall skipifsilent
