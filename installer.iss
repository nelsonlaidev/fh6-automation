; Inno Setup script for FH6 Automation

#define MyAppName "FH6 Automation"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "nelsonlaidev"
#define MyAppURL "https://github.com/nelsonlaidev/fh6-automation"
#define MyAppExeName "FH6Automation.exe"

[Setup]
AppId={{A3F8B2E1-7C4D-4A5E-9B1F-2D6E8C3A7B4F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\FH6Automation
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=FH6Automation_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\FH6Automation\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
