$taskName = "ArgusMQTT"
$taskDescription = "Starts ArgusMQTT.exe at boot with administrative privileges"
$taskAction = New-ScheduledTaskAction -Execute "C:\Argus\ArgusMQTT.exe"
$taskTrigger = New-ScheduledTaskTrigger -AtStartup
$taskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Description $taskDescription -Action $taskAction -Trigger $taskTrigger -Principal $taskPrincipal -Settings $taskSettings