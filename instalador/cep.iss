; Instalador de CEP (Inno Setup 6). Lo compila construir.bat:
;   ISCC.exe /DFuente=<carpeta dist\CEP de PyInstaller> instalador\cep.iss
; Instala para el usuario actual (no pide permisos de administrador). Los datos quedan en
; C:\Users\<usuario>\CEP (fuera de OneDrive) y NO se borran al desinstalar.

#define Nombre "CEP — Control Estadístico de Procesos"
#define Version "1.0.0"
#ifndef Fuente
  #define Fuente "..\dist\CEP"
#endif

[Setup]
AppId={{6F0C2B7E-3D41-4E8A-9B52-2C7A1E5D9F30}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher=Trabajo final de Control Estadístico de Procesos
DefaultDirName={autopf}\CEP
DefaultGroupName=CEP
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=salida
OutputBaseFilename=CEP-Setup-{#Version}
SetupIconFile=cep.ico
UninstallDisplayIcon={app}\CEP.exe
UninstallDisplayName={#Nombre}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
es.FinishedLabel=CEP quedó instalado. Ábrelo desde el acceso directo «CEP».%n%nTus datos se guardan en la carpeta CEP de tu usuario ({%USERPROFILE}\CEP: base de datos, reportes y respaldos) y se conservan aunque desinstales o actualices el programa.%n%nPara los informes PDF con LaTeX instala MiKTeX (opcional): sin él, el PDF se genera con el formato de respaldo.

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "{#Fuente}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\CEP"; Filename: "{app}\CEP.exe"; Comment: "{#Nombre}"
Name: "{autodesktop}\CEP"; Filename: "{app}\CEP.exe"; Comment: "{#Nombre}"; Tasks: escritorio

[Run]
Filename: "{app}\CEP.exe"; Description: "Abrir CEP ahora"; Flags: nowait postinstall skipifsilent

[Code]
{ CEP muestra su ventana con Microsoft Edge WebView2 (incluido en Windows 11 y en Windows 10 actualizado). }
function TieneWebView2(): Boolean;
var
  Version: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) or
    RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
  Result := Result and (Version <> '') and (Version <> '0.0.0.0');
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not TieneWebView2() then
    MsgBox('Este equipo no tiene Microsoft Edge WebView2, que CEP usa para mostrar su ventana.' + #13#10 +
           'Descárgalo gratis desde https://go.microsoft.com/fwlink/p/?LinkId=2124703 e instálalo antes de abrir CEP.',
           mbInformation, MB_OK);
end;
