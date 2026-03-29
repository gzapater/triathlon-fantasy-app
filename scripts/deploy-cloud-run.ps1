param(
    [string]$ServiceName = "tripredict",
    [string]$Region = "europe-west1",
    [string]$ProjectId = $env:GCP_PROJECT_ID,
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$FlaskSecretKey = $env:FLASK_SECRET_KEY,
    [string]$GoogleClientId = $env:GOOGLE_CLIENT_ID,
    [int]$MaxInstances = 3
)

$ErrorActionPreference = "Stop"

if (-not $ProjectId) {
    throw "Falta GCP_PROJECT_ID. Define esa variable o pasa -ProjectId."
}

if (-not $DatabaseUrl) {
    throw "Falta DATABASE_URL. Usa la URL de Postgres de Supabase."
}

if (-not $FlaskSecretKey) {
    throw "Falta FLASK_SECRET_KEY."
}

if (-not $GoogleClientId) {
    throw "Falta GOOGLE_CLIENT_ID."
}

$tempFile = Join-Path ([System.IO.Path]::GetTempPath()) ("cloudrun-env-" + [guid]::NewGuid().ToString() + ".yaml")
$escapedDatabaseUrl = $DatabaseUrl.Replace("'", "''")
$escapedSecret = $FlaskSecretKey.Replace("'", "''")
$escapedGoogleClientId = $GoogleClientId.Replace("'", "''")

@"
DATABASE_URL: '$escapedDatabaseUrl'
FLASK_SECRET_KEY: '$escapedSecret'
GOOGLE_CLIENT_ID: '$escapedGoogleClientId'
"@ | Set-Content -Path $tempFile -Encoding UTF8

try {
    gcloud config set project $ProjectId | Out-Null

    gcloud run deploy $ServiceName `
        --source . `
        --region $Region `
        --allow-unauthenticated `
        --min-instances 0 `
        --max-instances $MaxInstances `
        --cpu 1 `
        --memory 512Mi `
        --concurrency 20 `
        --env-vars-file $tempFile
}
finally {
    if (Test-Path $tempFile) {
        Remove-Item $tempFile -Force
    }
}
