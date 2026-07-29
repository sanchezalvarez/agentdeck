' Launches heartbeat.ps1 without a console window.
'
' Task Scheduler creates the console before PowerShell can act on
' -WindowStyle Hidden, so running powershell.exe directly flashes a window on
' screen every time the task fires. wscript.exe is a GUI process and allocates
' no console, so starting PowerShell from here with intWindowStyle 0 keeps the
' run invisible. (Setting the task itself to "run whether the user is logged on
' or not" would also work, but that change needs administrator rights.)
Dim shell, script
Set shell = CreateObject("WScript.Shell")
script = "C:\agent-deck\scripts\heartbeat.ps1"

' 0 = hidden window, False = do not wait for it to finish.
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & script & """", 0, False
