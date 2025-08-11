# Params for the SteamCMD installation directory, start.bat content, and server install path
param (
    [string]$steamCmdPath,
    [string]$installPath,
    [string]$startBatContent
)

# Create SteamCMD folder if it doesn't exist
if (-not (Test-Path $steamCmdPath)) {
    New-Item -Path $steamCmdPath -ItemType Directory
}

$steamCmdExecutable = Join-Path $steamCmdPath 'steamcmd.exe'
$steamCmdJustInstalled = $false

# Install SteamCMD if missing
if (-not (Test-Path $steamCmdExecutable)) {
    Write-Host 'Downloading SteamCMD...'
    $steamCmdUrl = 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip'
    $steamCmdZip = Join-Path $env:TEMP 'steamcmd.zip'

    Invoke-WebRequest -Uri $steamCmdUrl -OutFile $steamCmdZip
    Expand-Archive -Path $steamCmdZip -DestinationPath $steamCmdPath
    Remove-Item -Path $steamCmdZip

    $steamCmdJustInstalled = $true
    Write-Host ('SteamCMD installed to ' + $steamCmdPath + '.')
} else {
    Write-Host ('SteamCMD already installed at ' + $steamCmdPath + '.')
}

# Create ARK install directory if it doesn't exist
if (-not (Test-Path $installPath)) {
    New-Item -Path $installPath -ItemType Directory
}

# Function to run SteamCMD
function Run-AppUpdate {
    param([string]$message)
    Write-Host $message
    & $steamCmdExecutable +force_install_dir "$installPath" +login anonymous +app_update 2430930 validate +quit -console
}

# First install/update run
Run-AppUpdate 'Running SteamCMD to install/update ARK server...'

# Check if the main executable exists, retry if not
$serverExePath = Join-Path $installPath 'ShooterGame\Binaries\Win64\ArkAscendedServer.exe'
if (-not (Test-Path $serverExePath)) {
    Write-Host 'Server executable not found — retrying download...'
    Run-AppUpdate 'Retrying SteamCMD app_update...'
}

# Final check
if (-not (Test-Path $serverExePath)) {
    Write-Host 'ERROR: ARK server executable still missing after install attempts.'
    exit 1
}

# Create start.bat after install is complete
$startBatPath = Join-Path (Split-Path $serverExePath -Parent) 'start.bat'
Set-Content -Path $startBatPath -Value $startBatContent
Write-Host ('start.bat created at ' + $startBatPath + '.')

Write-Host 'ARK server installed or updated successfully.'
Write-Host ('You can start the ARK server with: ' + $startBatPath)
