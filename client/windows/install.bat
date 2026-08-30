@echo off
setlocal EnableExtensions DisableDelayedExpansion
net session >nul 2>&1 || (echo Please run as Administrator. & exit /b 1)
set "CERTHUB_API=@@API_ENDPOINT@@"
set "CERTHUB_ENROLLMENT=@@ENROLLMENT_TOKEN@@"
set "CERTHUB_DIR=%ProgramData%\CertHub"
if not exist "%CERTHUB_DIR%" mkdir "%CERTHUB_DIR%"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri '%CERTHUB_API%?action=client_windows' -OutFile '%CERTHUB_DIR%\agent.ps1'; & '%CERTHUB_DIR%\agent.ps1' -Enroll -ApiEndpoint '%CERTHUB_API%' -EnrollmentToken '%CERTHUB_ENROLLMENT%'"
if not "%errorlevel%"=="0" exit /b %errorlevel%
schtasks /Create /F /SC ONSTART /TN "CertHub Certificate Sync" /RU SYSTEM /RL HIGHEST /TR "powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File \"%CERTHUB_DIR%\agent.ps1\" -Daemon"
schtasks /Run /TN "CertHub Certificate Sync"
set "CERTHUB_ENROLLMENT="
echo CertHub Agent 0.3.3 installed.
