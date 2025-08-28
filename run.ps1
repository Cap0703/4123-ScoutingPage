# Get the current directory of the PowerShell script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$stdoutPath = Join-Path $scriptDir "cloudflared_stdout.txt"
$stderrPath = Join-Path $scriptDir "cloudflared_stderr.txt"
$tunnelFile = Join-Path $scriptDir "tunnel.txt"

# Start the Python app (keep handle)
Write-Output "Starting Flask server..."
$flask = Start-Process python -ArgumentList "server.py" -PassThru -NoNewWindow

# Start Cloudflare tunnel (keep handle)
Write-Output "Starting Cloudflare tunnel..."
$cloudflared = Start-Process "cloudflared" -ArgumentList "tunnel", "--url", "http://localhost:3000" `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden -PassThru

# Wait a few seconds for Cloudflare to spin up
Start-Sleep -Seconds 5

# Read the tunnel URL from stderr (where cloudflared logs it)
$tunnelUrl = $null
for ($i = 0; $i -lt 10; $i++) {
    if (Test-Path $stderrPath) {
        $lines = Get-Content $stderrPath
        foreach ($line in $lines) {
            if ($line -match "https://[a-zA-Z0-9\-]+\.trycloudflare\.com") {
                $tunnelUrl = $Matches[0]
                break
            }
        }
    }
    if ($tunnelUrl) { break }
    Start-Sleep -Seconds 1
}

# Show result and write URL to tunnel.txt only if it's new
if ($tunnelUrl) {
    Write-Output "Tunnel URL: $tunnelUrl"
    
    # Check if tunnel.txt exists and read current URL
    $currentUrl = $null
    if (Test-Path $tunnelFile) {
        $currentUrl = Get-Content $tunnelFile -Raw
    }
    
    # Only write if URL is new or different
    if ($currentUrl -ne $tunnelUrl) {
        Set-Content -Path $tunnelFile -Value $tunnelUrl
        Write-Output "Tunnel URL saved to $tunnelFile"
        
        # Push to GitHub if URL changed
        Write-Output "Pushing new URL to GitHub..."
        try {
            # Add the changed file
            git add $tunnelFile
            
            # Commit with message
            $commitMessage = "Update tunnel URL: $tunnelUrl"
            git commit -m $commitMessage
            
            # Push to remote
            git push
            
            Write-Output "Successfully pushed new URL to GitHub"
        }
        catch {
            Write-Error "Failed to push to GitHub: $($_.Exception.Message)"
        }
    } else {
        Write-Output "Tunnel URL unchanged, not updating $tunnelFile or GitHub"
    }
} else {
    Write-Error "Failed to extract Cloudflare tunnel URL from stderr."
}

Write-Output "`nServices running. Press Ctrl+C to stop."

# --- Graceful shutdown handler ---
$stopProcesses = {
    Write-Output "`nStopping services..."
    if ($flask -and !$flask.HasExited) { 
        $flask.Kill()
        Write-Output "Flask stopped."
    }
    if ($cloudflared -and !$cloudflared.HasExited) { 
        $cloudflared.Kill()
        Write-Output "Cloudflare tunnel stopped."
    }
    Write-Output "Shutdown complete."
    exit
}

# Register Ctrl+C handler
$null = Register-EngineEvent PowerShell.Exiting -Action $stopProcesses
$null = Register-EngineEvent ConsoleCancelEvent -Action { $stopProcesses.Invoke() }

# Wait for Flask to exit naturally
try {
    $flask.WaitForExit()
}
finally {
    & $stopProcesses
}