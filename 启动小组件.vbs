' 静默启动 DDL 桌面小组件（无控制台窗口）
' 双击本文件即可；使用固定的 Python 解释器，避免 .pyw 关联到缺少 PySide6 的 Python。
Option Explicit

Dim shell, fso, root, pythonw, script
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
script = fso.BuildPath(root, "run.pyw")

pythonw = "D:\Softwares\anaconda\pythonw.exe"
If Not fso.FileExists(pythonw) Then
    pythonw = "pythonw.exe"
End If

shell.CurrentDirectory = root
shell.Run """" & pythonw & """ """ & script & """", 0, False
