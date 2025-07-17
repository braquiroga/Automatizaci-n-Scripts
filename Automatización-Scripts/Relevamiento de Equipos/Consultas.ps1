# Inicializacion de variables
# Obtener el nombre del equipo y el nombre del usuario
$nombreEquipo = $env:COMPUTERNAME
$nombreUsuario = $env:USERNAME

# Obtener el numero de serie del equipo
$numeroSerie = (Get-WmiObject -Class Win32_Bios).SerialNumber

# Determinar el tipo de computadora (PC, NB, AIO)
$systemType = (Get-CimInstance -ClassName Win32_ComputerSystem).PCSystemType
switch ($systemType) {
    1 { $tipoEquipo = "Desktop" }
    2 { $tipoEquipo = "Mobile" }
    3 { $tipoEquipo = "All-in-One" }
    default { $tipoEquipo = "Desconocido" }
}

# Obtener el tipo de memoria RAM desde WMI
$memoryType = Get-WmiObject -Class Win32_PhysicalMemory | Select-Object -First 1 -ExpandProperty SMBIOSMemoryType
switch ($memoryType) {
    26 { $type = "DDR4" }
    24 { $type = "DDR3" }
    21 { $type = "DDR2" }
    default { $type = "Unknown" }
}

# Obtener informacion del sistema
$domain = Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object -ExpandProperty Domain
$ip = Test-Connection -ComputerName (hostname) -Count 1 | Select-Object -ExpandProperty IPV4Address | Select-Object -ExpandProperty IPAddressToString
$licenseStatus = (Get-WmiObject -Query "SELECT LicenseStatus FROM SoftwareLicensingProduct WHERE PartialProductKey IS NOT NULL" | Select-Object -First 1).LicenseStatus
switch ($licenseStatus) {
    0 { $status = "UnLicensed" }
    1 { $status = "Licensed" }
    2 { $status = "OOBGrace" }
    3 { $status = "OOTGrace" }
    4 { $status = "NonGenuineGrace" }
    5 { $status = "NotActivated" }
    6 { $status = "ExtendedGrace" }
    default { $status = "Unknown License Status" }
}

# Obtener informacion del procesador y sistema
$processorName = (Get-WmiObject Win32_Processor | Select-Object -ExpandProperty Name)
$systemModel = (Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object -ExpandProperty Model)
$baseboardManufacturer = (Get-WmiObject Win32_BaseBoard | Select-Object -ExpandProperty Manufacturer)
$baseboardProduct = (Get-WmiObject Win32_BaseBoard | Select-Object -ExpandProperty Product)
$osCaption = (Get-WmiObject -Class Win32_OperatingSystem).Caption
$osInstallDate = (Get-CimInstance Win32_OperatingSystem).InstallDate.ToString("dd/MM/yy")

# Obtener informacion de RAM
$ramSizes = Get-WmiObject Win32_PhysicalMemory | Select-Object -ExpandProperty Capacity
$ramSizesGB = $ramSizes | ForEach-Object { "{0:N2} GB" -f ($_ / 1GB) }
$ram = $ramSizesGB -join " + "

$ramSpeeds = Get-WmiObject Win32_PhysicalMemory | Select-Object -ExpandProperty Speed
$ramSpeedsList = $ramSpeeds -join " "

$ramManufacturers = Get-WmiObject Win32_PhysicalMemory | Select-Object -ExpandProperty Manufacturer
$ramManufacturersList = $ramManufacturers -join " "

# Obtener direcciones MAC de adaptadores
$macAddressesList = (Get-NetAdapter | Where-Object {$_.Name -Match 'Ethernet'} | Select-Object -ExpandProperty MacAddress) -join " "
$wifiMacAddressesList = (Get-NetAdapter | Where-Object {$_.Name -Match 'Wi-Fi'} | Select-Object -ExpandProperty MacAddress) -join " "

# Obtener informacion de controladores de video
$videoControllersList = (Get-WmiObject win32_VideoController | Where-Object { $_.DeviceID -match 'VideoController' } | Select-Object -ExpandProperty Name) -join " "

# Obtener informacion de discos fisicos
$diskInfo = Get-PhysicalDisk | Where-Object { $_.BusType -ne "USB" }
$diskNamesList = $diskInfo | Select-Object -ExpandProperty FriendlyName
$diskTypesList = $diskInfo | Select-Object -ExpandProperty MediaType
$diskSizesGBList = $diskInfo | ForEach-Object { "{0:N2} GB" -f ($_.Size / 1GB) }

# Convertir listas a cadenas concatenadas
$diskNames = if ($diskNamesList) { $diskNamesList -join " | " } else { "-" }
$diskTypes = if ($diskTypesList) { $diskTypesList -join " | " } else { "-" }
$diskSizesGB = if ($diskSizesGBList) { $diskSizesGBList -join " + " } else { "-" }

# Obtener el ID de AnyDesk
$AnyDeskService = Get-WmiObject -Query "SELECT * FROM Win32_Service WHERE Name LIKE 'AnyDesk%'"
if ($AnyDeskService) {
    $BinPath = $AnyDeskService.PathName -replace ' --service',''
    $IdFile = "$env:TEMP\anydesk.id"
    Start-Process -FilePath $BinPath -ArgumentList '--get-id' -Wait -RedirectStandardOutput $IdFile
    $ANY = Get-Content -Path $IdFile
} else {
    $ANY = "AnyDesk no esta instalado."
}

# Fecha y hora de relevamiento
$fechaRelevamiento = Get-Date -Format "dd-MM-yyyy"

# Crear carpeta con el nombre del equipo y la fecha y hora de relevamiento en la misma ubicación que el script
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$folderPath = "$scriptPath\$nombreEquipo-$fechaRelevamiento ($ip)"
New-Item -ItemType Directory -Path $folderPath -Force | Out-Null

# Crear un objeto PSObject con los resultados aplanados
$result = [PSCustomObject]@{
"Nombre del Equipo"                  = $nombreEquipo
"Nombre de Usuario"                  = $nombreUsuario
"Numero de Serie"                    = $numeroSerie
"Tipo de Equipo"                     = $tipoEquipo
"Estado de Licencia"                 = $status
"Descripcion del Sistema Operativo"  = $osCaption
"Fecha de Instalacion del SO"        = $osInstallDate
"Modelo de Sistema"                  = $systemModel
"Procesador"                         = $processorName
"Tipo de Memoria RAM"                = $type
"RAM"                                = $ram
"Velocidades de RAM"                 = $ramSpeedsList
"Fabricantes de RAM"                 = $ramManufacturersList
"Direccion MAC (Ethernet)"           = $macAddressesList
"Direccion MAC (Wi-Fi)"              = $wifiMacAddressesList
"Dominio"                            = $domain
"IP"                                 = $ip
"Discos"                             = $diskNames
"Tipos de Disco"                     = $diskTypes
"Tamanos de Disco"                   = $diskSizesGB
"Controladores de Video"             = $videoControllersList
"ID de AnyDesk"                      = $ANY
"Fecha de Relevamiento"              = $fechaRelevamiento
"Observaciones"                      = $observaciones  
}
# Exportar los resultados a un archivo CSV en la carpeta creada
$resultsArray = @($result)
$csvFileName = "$folderPath\Caracteristicas_Del_Equipo.csv"
$resultsArray | Export-Csv -Path $csvFileName -NoTypeInformation -Encoding UTF8 -Delimiter ';' | Out-Null

# Mensaje de confirmación
Write-Host "El archivo CSV ha sido creado en: $csvFileName"



######## Printers #######

# Crear una lista para almacenar los datos de las impresoras
$printerList = @()

# Obtener impresoras instaladas en el sistema
$printers = Get-WmiObject -Query "SELECT * FROM Win32_Printer"

# Recorrer cada impresora y agregar la información a la lista
foreach ($printer in $printers) {
    $printerName = $printer.Name
    $printerDriver = $printer.DriverName
    $printerShared = $printer.Shared
    $printerPortName = $printer.PortName

    # Determinar si es una impresora de red o USB
    if ($printerPortName -match "^USB") {
        $connectionType = "USB"
        $printerIP = "N/A"  # No tiene IP si es USB
    } elseif ($printerPortName -match "^IP_") {
        $connectionType = "Red"
        $printerIP = $printerPortName -replace "^IP_", ""
    } else {
        $connectionType = "Desconocido"
        $printerIP = "N/A"
    }

    # Crear un objeto con la información de la impresora
    $printerData = [PSCustomObject]@{
        "Impresora"     = $printerName
        "Modelo"        = $printerDriver
        "Conexión"      = $connectionType
        "IP"            = $printerIP
        "Compartida"    = $printerShared
    }

    # Agregar la información a la lista
    $printerList += $printerData
}

# Obtener la ruta de la carpeta anterior (donde se guardó el CSV anterior)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

# Definir la ruta completa del archivo CSV en la carpeta creada
$csvFilePath = "$folderPath\Impresoras_Instaladas.csv"

# Exportar los datos de las impresoras a un archivo CSV
$printerList | Export-Csv -Path $csvFilePath -NoTypeInformation -Delimiter ";"

Write-Output "El archivo CSV se ha generado en: $csvFilePath"

######### Apps ##########

# Obtener la lista de programas instalados desde el registro
$programs = Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" |
            Select-Object DisplayName, DisplayVersion, Publisher, InstallDate

# Filtrar programas para omitir los predeterminados de Windows
$defaultWindowsApps = @(
    "Microsoft .NET Framework",
    "Microsoft Visual C++",
    "Windows Defender",
    "Microsoft Edge",
    "Windows Media Player",
    "Windows Photos",
    "Windows Store"
)

$filteredPrograms = $programs | Where-Object {
    $_.DisplayName -and 
    (-not ($defaultWindowsApps -contains $_.DisplayName))
}

# Exportar los resultados a un archivo CSV en la carpeta creada
$csvFilePath = "$folderPath\Programas_Instalados.csv"
$filteredPrograms | Export-Csv -Path $csvFilePath -NoTypeInformation -Encoding UTF8 -Delimiter ';'

Write-Output "El archivo CSV se ha generado en: $csvFilePath"
