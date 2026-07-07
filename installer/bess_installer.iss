; Inno Setup Script para BESS Simulator
; Requiere: Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;
; Para compilar:
;   1. Ejecutar primero: python installer/build_package.py
;   2. Abrir este archivo con Inno Setup Compiler
;   3. Compilar -> genera BessSimulatorSetup.exe

[Setup]
AppName=BESS Simulator
AppVersion=0.1.0
AppPublisher=Equipo Interno
DefaultDirName={autopf}\BessSimulator
DefaultGroupName=BESS Simulator
UninstallDisplayIcon={app}\launch_bess.bat
OutputDir=..\dist
OutputBaseFilename=BessSimulatorSetup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Files]
Source: "..\dist\bess-simulator\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BESS Simulator"; Filename: "{app}\launch_bess.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\BESS Simulator"; Filename: "{app}\launch_bess.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\launch_bess.bat"; Description: "Iniciar BESS Simulator"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; NO eliminar data/ para preservar simulaciones guardadas
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\src"
Type: files; Name: "{app}\launch_bess.bat"
