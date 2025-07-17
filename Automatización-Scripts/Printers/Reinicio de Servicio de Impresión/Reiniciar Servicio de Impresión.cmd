@Echo Off
Cls

REMStop Citrix Print Manager
Stop cpsvc

REM Stop Print Spooler
Net Stop Spooler

REM Kill Print Spooler - requires KILL from Resource Kit

REM Delete all hung print jobs - also removes hung printers.
Del /F /Q "%SYSTEMROOT%\SYSTEM32\SPOOL\PRINTERS\*.*"

REM Restart the Print Spooler
Net Start Spooler

REM Start Citrix Print Manager
Net Start cpsvc

PAUSE
REM Exit the script
Exit

