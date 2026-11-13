Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strPath = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath

' Argumentos por defecto: ocultar la consola
args = "--ocultar-consola"

' Si se pasan argumentos adicionales (por ejemplo --no-browser desde Inicio de Windows), adjuntarlos
If WScript.Arguments.Count > 0 Then
    For i = 0 To WScript.Arguments.Count - 1
        args = args & " " & WScript.Arguments(i)
    Next
End If

cmdLine = "cmd.exe /c """"" & strPath & "\iniciar_servidor_web.bat"" " & args & """"
WshShell.Run cmdLine, 0, False
