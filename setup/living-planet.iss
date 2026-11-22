; This is the Inno Setup source script for developers, not the installer executable.
; End users launch SETUPGAME.exe for the current Windows release.
#pragma code_page = 65001
#define AppVersion "8.5.0"
#define AppName "Living Planet"

[Setup]
AppId={{2E7A9BB6-4C72-48FC-AD3A-801B5D33A801}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=TPECKA180
DefaultDirName={localappdata}\Programs\Living Planet
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\LivingPlanet.exe
SetupIconFile=..\docs\assets\living-planet.ico
OutputDir=..\dist\installer
OutputBaseFilename=SETUPGAME
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
Uninstallable=yes

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"; Flags: unchecked

[Files]
Source: "..\dist\LivingPlanet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\LivingPlanet.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\assets\living-planet.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\LivingPlanet.exe"; WorkingDir: "{app}"; IconFilename: "{app}\_internal\assets\living-planet.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\LivingPlanet.exe"; Description: "Запустить {#AppName}"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent
