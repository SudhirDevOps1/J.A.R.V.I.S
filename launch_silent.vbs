' J.A.R.V.I.S. Silent Background Launcher
' Runs start_jarvis.bat completely hidden (no console window) while preserving standard OS handles
Set FSO = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptDir
WshShell.Run "cmd.exe /c start_jarvis.bat", 0, False
