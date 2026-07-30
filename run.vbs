Set WshShell = CreateObject("WScript.Shell")
' 0 = ウィンドウ非表示 (サイレント実行)
WshShell.Run "cmd /c setup_and_run.bat", 0, False
