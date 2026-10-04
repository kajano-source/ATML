; ATML 1.2.0 — Inno Setup script (Windows).
; Build with Inno Setup 6: iscc installer\windows\atml.iss
#define MyAppName "ATML"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "ATML contributors"

[Setup]
AppId={{A7A11C00-0000-4000-8000-ATML1000}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\ATML
DisableProgramGroupPage=yes
OutputBaseFilename=atml-1.2.0-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes

[Files]
; Payload trees (empty dirs are fine — installer still creates the layout).
Source: "..\..\compiler\*"; DestDir: "{app}\compiler"; Flags: recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\..\runtime\*"; DestDir: "{app}\runtime"; Flags: recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\..\examples\*"; DestDir: "{app}\examples"; Flags: recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\..\vscode-atml\*"; DestDir: "{app}\vscode-atml"; Flags: recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\gui_installer.py"; DestDir: "{app}\installer"; Flags: skipifsourcedoesntexist
Source: "..\cli_install.py"; DestDir: "{app}\installer"; Flags: skipifsourcedoesntexist
; Shim installed to {app}\bin by [Code] below; bundled vsix (optional).
Source: "..\..\vscode-atml\*.vsix"; DestDir: "{app}\vscode-atml"; Flags: skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\ATML"; Filename: "{app}\bin\atml.bat"

[Registry]
; .atml file association.
Root: HKCU; Subkey: "Software\Classes\.atml"; ValueType: string; ValueName: ""; ValueData: "ATML.Document"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\ATML.Document"; ValueType: string; ValueName: ""; ValueData: "ATML template"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\ATML.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\bin\atml.bat"" ""%1"""

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  BinDir, Shim: String;
  ShimContents: AnsiString;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    BinDir := ExpandConstant('{app}\bin');
    ForceDirectories(BinDir);
    Shim := BinDir + '\atml.bat';
    ShimContents := '@echo off' + #13#10 + 'python "' + ExpandConstant('{app}') + '\compiler\atmlc.py" %*' + #13#10;
    SaveStringToFile(Shim, ShimContents, False);
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\compiler"
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\examples"
