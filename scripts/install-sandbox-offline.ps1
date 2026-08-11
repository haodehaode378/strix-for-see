param(
  [Parameter(Position = 0)]
  [string]$ArchivePath,
  [Parameter(Position = 1)]
  [string]$Version
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker CLI was not found. Install and start Docker Desktop first."
}

docker info --format "{{.ServerVersion}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "Docker Desktop is not running."
}

if (-not $ArchivePath) {
  $archive = Get-ChildItem -LiteralPath $PSScriptRoot -Filter "strix-sandbox-*-amd64.tar.gz" |
    Select-Object -First 1
  if (-not $archive) {
    throw "Place the Sandbox .tar.gz archive beside this script, or pass its path."
  }
  $ArchivePath = $archive.FullName
}

$resolvedArchive = (Resolve-Path -LiteralPath $ArchivePath).Path
if (-not $Version) {
  $archiveName = [System.IO.Path]::GetFileName($resolvedArchive)
  if ($archiveName -notmatch '^strix-sandbox-(?<version>\d+\.\d+\.\d+)-amd64\.tar\.gz$') {
    throw "The archive name does not contain a Sandbox version. Pass the version as the second argument."
  }
  $Version = $Matches.version
}
$runtimeImage = "ghcr.io/usestrix/strix-sandbox:$Version"

Write-Host "Loading Strix Sandbox from $resolvedArchive"
docker load --input $resolvedArchive
if ($LASTEXITCODE -ne 0) {
  throw "Docker could not import the Sandbox archive."
}

docker image inspect $runtimeImage --format "{{.Id}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "The archive loaded, but the expected Strix Sandbox tag was not found."
}

Write-Host "Strix Sandbox is ready: $runtimeImage"
