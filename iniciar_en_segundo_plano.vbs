Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strPath = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath
WshShell.Run "cmd.exe /c """ & strPath & "\iniciar_servidor_web.bat"" --ocultar-consola --no-browser", 0, False
