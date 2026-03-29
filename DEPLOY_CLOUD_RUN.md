# Deploy en Cloud Run + Supabase

## 1. Que necesitas

- Un proyecto de Google Cloud con facturacion activada.
- Un proyecto de Supabase.
- `gcloud` instalado y autenticado.
- Python 3.11 local para correr migraciones y seed.

Antes del primer deploy, habilita los servicios necesarios:

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 2. Base de datos en Supabase

Usa una URL de Postgres de Supabase.

- Recomendado para Cloud Run: `Session pooler` (`pooler.supabase.com:5432`).
- Tambien funcionara `Transaction pooler` (`:6543`) porque la app ya desactiva prepared statements para PgBouncer.

Guarda la URL en `DATABASE_URL`, una clave aleatoria larga en `FLASK_SECRET_KEY` y el client ID web de Google en `GOOGLE_CLIENT_ID`.

Ejemplo en PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://postgres.xxx:[TU_PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres"
$env:FLASK_SECRET_KEY = "cambia-esto-por-una-clave-larga-y-aleatoria"
$env:GOOGLE_CLIENT_ID = "tu-client-id.apps.googleusercontent.com"
```

## 3. Login con Google

En Google Cloud Console:

- Ve a `APIs y servicios > Pantalla de consentimiento OAuth` y configura la app.
- Luego ve a `APIs y servicios > Credenciales > Crear credenciales > ID de cliente OAuth`.
- Tipo: `Aplicación web`.
- `Authorized JavaScript origins`:
  - `http://localhost:5000`
  - `https://tripredict-171926740552.europe-west1.run.app`
- No hace falta `Authorized redirect URIs` para Google Identity Services con ID token.

## 4. Migraciones y seed

Antes del primer deploy, deja la base preparada:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.venv\Scripts\python.exe backend\manage.py db upgrade
.venv\Scripts\python.exe backend\manage.py seed_data
```

## 5. Despliegue a Cloud Run

Configura tu proyecto:

```powershell
$env:GCP_PROJECT_ID = "tu-proyecto-gcp"
```

Si todavia no has autenticado `gcloud`:

```powershell
gcloud auth login
gcloud config set project $env:GCP_PROJECT_ID
```

Luego despliega:

```powershell
.\scripts\deploy-cloud-run.ps1 -ServiceName tripredict -Region europe-west1
```

El script:

- construye la imagen desde el `Dockerfile`
- despliega con `min instances = 0`
- deja variables de entorno en Cloud Run

## 6. Notas importantes

- Este repo no deberia versionar `.flaskenv` ni otros ficheros con secretos.
- Si vas a usar Supabase Free, el proyecto puede pausarse por inactividad.
- Cloud Run solo podra arrancar si `backend.app:app` importa correctamente.
- `backend/app.py` ya esta preparado para leer `DATABASE_URL` y `FLASK_SECRET_KEY` desde el entorno y usar SQLite local solo como fallback de desarrollo.
