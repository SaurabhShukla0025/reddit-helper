$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$systemSid = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')
$adminSid = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')
$protectedFiles = @()
# Exact local application files only. Never recurse or alter the repository's ACL.
foreach ($name in @('config.yaml', 'queue.db', 'queue.db-journal', 'queue.db-wal', 'queue.db-shm', '.credentials.bin')) {
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $name))
    if (-not $candidate.StartsWith($projectRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Path escaped project.' }
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $item = Get-Item -LiteralPath $candidate -Force
    if ($item.PSIsContainer -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { throw "Refusing linked/directory target: $name" }
    $acl = New-Object System.Security.AccessControl.FileSecurity
    $acl.SetOwner($currentSid)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @($currentSid, $systemSid, $adminSid)) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $candidate -AclObject $acl
    $verified = Get-Acl -LiteralPath $candidate
    if (-not $verified.AreAccessRulesProtected) { throw "ACL protection failed: $name" }
    $protectedFiles += $name
}
@{protected_files=$protectedFiles; verified_at=(Get-Date).ToString('o'); disk_encryption='not verified'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot '.data-protection.json') -Encoding utf8
Write-Output ('Restricted access to: ' + ($protectedFiles -join ', ') + '. Disk encryption remains unverified. Repeat for newly created files.')
