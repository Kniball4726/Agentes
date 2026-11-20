Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strPath = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath

' Argumentos por defecto: ocultar la consola
args = "--ocultar-consola"

' Permitir únicamente flags CLI conocidos (previene inyección de comandos en cmd.exe)
Set rxSafeFlag = New RegExp
rxSafeFlag.Pattern = "^--(no-browser|sin-navegador|silent|no-tray|sin-tray|https|http|qa|desktop|force|forzar|reiniciar|restart)$"
rxSafeFlag.IgnoreCase = True

If WScript.Arguments.Count > 0 Then
    For i = 0 To WScript.Arguments.Count - 1
        argVal = Trim(CStr(WScript.Arguments(i)))
        If rxSafeFlag.Test(argVal) Then
            args = args & " " & argVal
        End If
    Next
End If

batPath = FSO.BuildPath(strPath, "iniciar_servidor_web.bat")
If FSO.FileExists(batPath) Then
    Set envProc = WshShell.Environment("Process")
    envProc("STOCKAGENT_BAT_PATH") = batPath
    cmdLine = "cmd.exe /c ""%STOCKAGENT_BAT_PATH%"" " & args
    WshShell.Run cmdLine, 0, False
End If
