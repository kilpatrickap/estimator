; Inno Setup Script for Estimator Pro
; Compiler: Inno Setup 6+ (ISCC)

#define MyAppName "Estimator Pro"
#define MyAppVersion "1.0.4"
#define MyAppPublisher "Kiltech"
#define MyAppURL "https://github.com/kilpatrickap/estimator"
#define MyAppExeName "Estimator_Pro.exe"

[Setup]
; Unique AppId (do NOT change this across versions so upgrades replace cleanly)
AppId={{D819C3A1-94E5-4B83-B75B-B7C934E84F01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=License - GNUv3
; Output configuration
OutputDir=Output
OutputBaseFilename=EstimatorPro_Setup
SetupIconFile=win_setup_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Permissions and update handling
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Standalone compiled executable
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Application & Setup icons
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "win_setup_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; License file
Source: "License - GNUv3"; DestDir: "{app}"; Flags: ignoreversion
; NOTE: DO NOT include .db files! Databases are auto-generated at runtime on first launch.

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Filename: "{app}\{#MyAppExeName}"; Flags: nowait postinstall
