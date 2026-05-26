$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

docker compose -f docker-compose-ollama-nvidia.yaml up -d
