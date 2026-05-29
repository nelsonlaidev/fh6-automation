; Inno Setup script for FH6 Automation

#define MyAppName "FH6 Automation"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
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
; 升級時自動關掉執行中的舊版本，安裝完再重新啟動。
; 搭配 app 內 `/VERYSILENT /SUPPRESSMSGBOXES` 呼叫，可實現無感更新。
CloseApplications=yes
RestartApplications=yes

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
; 互動安裝：Finish 頁顯示「啟動 App」勾選（預設勾起）。
; 靜默安裝（/VERYSILENT）：因為沒有 skipifsilent flag，postinstall entry 會直接執行，
; 安裝完成後自動啟動新版本，達成 in-app 無感更新。
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall
