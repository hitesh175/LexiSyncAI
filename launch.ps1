param([switch]$Headless)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

try {
    $env:PYTHONUTF8 = '1'
    if (-not $env:OMP_NUM_THREADS) { $env:OMP_NUM_THREADS = '4' }
    if (-not $env:OLLAMA_MODEL) {
        $env:OLLAMA_MODEL = 'kamekichi128/qwen3-4b-instruct-2507:latest'
    }

    if (-not $env:OLLAMA_URL) {
        $ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
        if (-not $ollama) {
            $ollamaPath = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
            if (-not (Test-Path -LiteralPath $ollamaPath)) {
                throw 'Install Ollama for Windows, then double-click this launcher again.'
            }
        } else {
            $ollamaPath = $ollama.Source
        }
        $env:OLLAMA_URL = 'http://127.0.0.1:11434'
        function Get-LocalModels {
            try {
                Invoke-RestMethod -Uri "$env:OLLAMA_URL/api/tags" -TimeoutSec 2
            } catch {
                $null
            }
        }
        $catalog = Get-LocalModels
        if ($null -eq $catalog) {
            Write-Host 'Starting Ollama...'
            Start-Process -FilePath $ollamaPath -ArgumentList 'serve' -WindowStyle Hidden
            for ($attempt = 0; $attempt -lt 20 -and $null -eq $catalog; $attempt++) {
                Start-Sleep -Milliseconds 500
                $catalog = Get-LocalModels
            }
        }
        if ($null -eq $catalog) { throw 'Ollama did not start. Open Ollama and try again.' }
        if ($env:OLLAMA_MODEL -notin @($catalog.models.name)) {
            Write-Host 'Downloading the local language model. This is a one-time setup.'
            & $ollamaPath pull $env:OLLAMA_MODEL
            if ($LASTEXITCODE -ne 0) { throw 'Ollama could not download the model.' }
        }
    }

    $venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $cachedPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    $workspaceRuntime = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\work\runtime'))
    if (Test-Path -LiteralPath 'local-runtime.txt') {
        $workspaceRuntime = (Get-Content -LiteralPath 'local-runtime.txt' -Raw).Trim()
    }
    if (-not $env:HF_HOME -and (Test-Path -LiteralPath (Join-Path (Split-Path $workspaceRuntime) 'hf'))) {
        $env:HF_HOME = Join-Path (Split-Path $workspaceRuntime) 'hf'
    }
    $hash = (Get-FileHash -LiteralPath 'requirements.txt' -Algorithm SHA256).Hash
    $sharedStamp = Join-Path $workspaceRuntime 'requirements.sha256'
    if ((Test-Path -LiteralPath $cachedPython) -and
        (-not (Test-Path -LiteralPath (Join-Path $workspaceRuntime 'streamlit\__init__.py')) -or
         -not (Test-Path -LiteralPath $sharedStamp) -or
         (Get-Content -LiteralPath $sharedStamp -Raw).Trim() -ne $hash)) {
        $workspaceRuntime = Join-Path $PSScriptRoot '.runtime'
        $stamp = Join-Path $workspaceRuntime 'requirements.sha256'
        if (-not (Test-Path -LiteralPath (Join-Path $workspaceRuntime 'streamlit\__init__.py')) -or
            -not (Test-Path -LiteralPath $stamp) -or (Get-Content -LiteralPath $stamp -Raw).Trim() -ne $hash) {
            Write-Host 'Preparing dependencies with the available Python runtime. This is a one-time setup.'
            & $cachedPython -m pip install --disable-pip-version-check --upgrade --target $workspaceRuntime -r requirements.txt
            if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed. Check your internet connection and run the launcher again.' }
            Set-Content -LiteralPath $stamp -Value $hash -Encoding ascii
        }
    }
    $headlessValue = $Headless.IsPresent.ToString().ToLowerInvariant()
    $port = 0
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        $port = $listener.LocalEndpoint.Port
    } finally {
        $listener.Stop()
    }
    $streamlitArgs = @('run', 'app.py', '--server.address=127.0.0.1', "--server.headless=$headlessValue", '--browser.gatherUsageStats=false', '--global.developmentMode=false', '--server.enableCORS=true', "--server.port=$port", "--browser.serverPort=$port")

    Write-Host "LexiSyncAI will be available at http://127.0.0.1:$port. Keep this window open while using the app."
    if ((Test-Path -LiteralPath $cachedPython) -and
        (Test-Path -LiteralPath (Join-Path $workspaceRuntime 'streamlit\__init__.py'))) {
        $env:LEXISYNC_LOCAL_RUNTIME = $workspaceRuntime
        & $cachedPython -c "import os,sys,runpy; sys.path.insert(0,os.environ['LEXISYNC_LOCAL_RUNTIME']); runpy.run_module('streamlit',run_name='__main__')" @streamlitArgs
    } else {
        if (-not (Test-Path -LiteralPath $venvPython)) {
            $created = $false
            if (Get-Command py.exe -ErrorAction SilentlyContinue) {
                foreach ($version in '-3.12', '-3.11') {
                    $previousPreference = $ErrorActionPreference
                    $ErrorActionPreference = 'Continue'
                    & py.exe $version -c "import venv" 2>$null
                    $ErrorActionPreference = $previousPreference
                    if ($LASTEXITCODE -ne 0) { continue }
                    & py.exe $version -m venv .venv
                    if ($LASTEXITCODE -eq 0) { $created = $true; break }
                }
            }
            if (-not $created) {
                throw 'Install Python 3.11 or 3.12 with the Windows Python launcher, then try again.'
            }
        }
        $stamp = Join-Path $PSScriptRoot '.venv\lexisync-requirements.sha256'
        if (-not (Test-Path -LiteralPath $stamp) -or (Get-Content -LiteralPath $stamp -Raw).Trim() -ne $hash) {
            Write-Host 'Installing the app dependencies. This is a one-time setup.'
            & $venvPython -m pip install -r requirements.txt
            if ($LASTEXITCODE -ne 0) { throw 'The dependency installation failed. Try again with an internet connection.' }
            Set-Content -LiteralPath $stamp -Value $hash -Encoding ascii
        }
        & $venvPython -m streamlit @streamlitArgs
    }
    if ($LASTEXITCODE -ne 0) { throw "The app stopped with exit code $LASTEXITCODE." }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}




