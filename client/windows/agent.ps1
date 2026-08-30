param([switch]$Enroll,[switch]$Sync,[switch]$Daemon,[string]$ApiEndpoint,[string]$EnrollmentToken)
$ErrorActionPreference='Stop'
$Root=Join-Path $env:ProgramData 'CertHub';$ConfigPath=Join-Path $Root 'config.protected';$Store=Join-Path $Root 'certificates';$StatePath=Join-Path $Root 'state.json'
New-Item -ItemType Directory -Force -Path $Root,$Store|Out-Null
function System-Info { return @{hostname=$env:COMPUTERNAME;os_name='Windows';os_version=[Environment]::OSVersion.VersionString;architecture=$env:PROCESSOR_ARCHITECTURE;agent_version='0.3.3'} }
function Protect-Config($Config){$b=[Text.Encoding]::UTF8.GetBytes(($Config|ConvertTo-Json -Compress));$p=[Security.Cryptography.ProtectedData]::Protect($b,$null,[Security.Cryptography.DataProtectionScope]::LocalMachine);[IO.File]::WriteAllBytes($ConfigPath,$p)}
function Read-Config{$p=[IO.File]::ReadAllBytes($ConfigPath);$b=[Security.Cryptography.ProtectedData]::Unprotect($p,$null,[Security.Cryptography.DataProtectionScope]::LocalMachine);return([Text.Encoding]::UTF8.GetString($b)|ConvertFrom-Json)}
function Call-Api($Uri,$Headers,$Body){return Invoke-RestMethod -Method POST -UseBasicParsing -Uri $Uri -Headers $Headers -ContentType 'application/json' -Body ($Body|ConvertTo-Json -Depth 6 -Compress)}
function Sync-Once([bool]$Force){
  $c=Read-Config;$h=@{'X-CertHub-Client'=$c.client_id;Authorization="Bearer $($c.auth_token)"};$pull=(Call-Api "$($c.api_endpoint)?action=pull" $h @{system=(System-Info)}).data
  $serverConfig=$pull.config;$last=0;if(Test-Path $StatePath){$last=(Get-Content $StatePath|ConvertFrom-Json).last_sync};$now=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  if((-not $Force)-and(($now-$last)-lt [int]$serverConfig.sync_interval_seconds)){return}
  foreach($a in $pull.certificates){
    $d=(Call-Api "$($c.api_endpoint)?action=bundle" $h @{certificate_id=$a.id;system=(System-Info)}).data;$dir=Join-Path (Join-Path $Store ([string]$a.id)) $d.version
    New-Item -ItemType Directory -Force -Path $dir|Out-Null;[IO.File]::WriteAllText((Join-Path $dir 'fullchain.pem'),$d.fullchain_pem,[Text.UTF8Encoding]::new($false));[IO.File]::WriteAllText((Join-Path $dir 'privkey.pem'),$d.private_key_pem,[Text.UTF8Encoding]::new($false))
    $acl=Get-Acl $dir;$acl.SetAccessRuleProtection($true,$false);$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new('SYSTEM','FullControl','ContainerInherit,ObjectInherit','None','Allow'));$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new('BUILTIN\Administrators','FullControl','ContainerInherit,ObjectInherit','None','Allow'));Set-Acl $dir $acl
    [IO.File]::WriteAllText((Join-Path (Split-Path $dir) 'current.txt'),$d.version,[Text.UTF8Encoding]::new($false))
    if($serverConfig.deploy_mode -eq 'custom' -and $serverConfig.download_path){$target=Join-Path $serverConfig.download_path ($d.name -replace '[^A-Za-z0-9._-]','_');New-Item -ItemType Directory -Force -Path $target|Out-Null;Copy-Item (Join-Path $dir 'fullchain.pem') (Join-Path $target 'fullchain.pem') -Force;Copy-Item (Join-Path $dir 'privkey.pem') (Join-Path $target 'privkey.pem') -Force}
  }
  @{last_sync=$now}|ConvertTo-Json -Compress|Set-Content -Encoding Ascii $StatePath
}
if($Enroll){if(-not $ApiEndpoint.StartsWith('https://')){throw 'Panel URL must use HTTPS.'};$r=Call-Api "$ApiEndpoint?action=enroll" @{} @{token=$EnrollmentToken;system=(System-Info)};if(-not $r.status){throw $r.error};Protect-Config @{api_endpoint=$r.data.api_endpoint;client_id=$r.data.client_id;auth_token=$r.data.auth_token}}
if($Sync){Sync-Once $true}
if($Daemon){while($true){try{Sync-Once $false}catch{Write-EventLog -LogName Application -Source 'CertHub' -EntryType Error -EventId 1 -Message $_.Exception.Message -ErrorAction SilentlyContinue};Start-Sleep -Seconds 300}}
