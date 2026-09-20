# NEXUS Deployment — Render

We are deploying NEXUS entirely on Render.

This deployment uses two interconnected Render Web Services running from this single repository:
1. **FastAPI Backend Web Service** (Python)
2. **Next.js Frontend Web Service** (Node.js)

MongoDB Atlas serves as the remote cloud database.

---

## Architecture Overview

```text
                    ┌─────────────────────────┐
                    │          User           │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Render                  │
                    │ Next.js Frontend        │
                    └────────────┬────────────┘
                                 │ HTTPS / API
                                 ▼
                    ┌─────────────────────────┐
                    │ Render                  │
                    │ FastAPI Backend         │
                    └────────────┬────────────┘
                                 │ PyMongo Driver
                                 ▼
                    ┌─────────────────────────┐
                    │ MongoDB Atlas Cluster   │
                    └─────────────────────────┘
```

---

## Service 1 — FastAPI Backend

- **Render service type:** `Web Service`
- **Environment / Runtime:** `Python`
- **Root Directory:** `backend`
- **Build command:**
  ```bash
  pip install -r requirements.txt
  ```
- **Production start command:**
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
- **Health check path:**
  ```text
  /health
  ```
- **Database health check path:**
  ```text
  /health/db
  ```
- **Required environment variables:**
  | Variable | Value / Description | Sensitive |
  | :--- | :--- | :--- |
  | `MONGODB_URI` | `<entered manually in Render dashboard>` | Yes (Secret) |
  | `PYTHON_VERSION` | `3.11.9` | No |

---

## Service 2 — Next.js Frontend

- **Render service type:** `Web Service`
- **Environment / Runtime:** `Node`
- **Root Directory:** `frontend`
- **Build command:**
  ```bash
  npm install && npm run build
  ```
- **Production start command:**
  ```bash
  npm run start -- -p $PORT
  ```
- **Required environment variables:**
  | Variable | Value / Description | Sensitive |
  | :--- | :--- | :--- |
  | `NEXT_PUBLIC_API_URL` | `https://YOUR-BACKEND.onrender.com` | No (Public) |
  | `NODE_VERSION` | `20.14.0` | No |

> **IMPORTANT:** In Next.js, `NEXT_PUBLIC_*` variables are inlined into the client bundle at build time. Ensure `NEXT_PUBLIC_API_URL` is set in the Render frontend service before triggering the build.

---

## Deployment Methods

### Option A — Automatic via Render Blueprint (`render.yaml`)

The repository includes a ready-to-use [`render.yaml`](file:///C:/Users/brije/Documents/NEXUS/render.yaml) blueprint at the root:

1. Push your repository to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com), click **New +** &rarr; **Blueprint**.
3. Connect your `NEXUS` repository. Render will automatically parse `render.yaml` and configure both services.
4. When prompted by Render:
   - Enter your real `MONGODB_URI` for the backend service.
   - Enter the backend URL for `NEXT_PUBLIC_API_URL` on the frontend service (e.g. `https://nexus-backend.onrender.com`).
5. Click **Apply**. Both services will build and deploy automatically.

---

### Option B — Manual Setup via Render Dashboard

If you prefer to configure the services manually:

#### 1. Deploy the Backend Service
1. In Render Dashboard, click **New +** &rarr; **Web Service**.
2. Select your repository.
3. Configure the service:
   - **Name:** `nexus-backend`
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Advanced &rarr; Health Check Path:** `/health`
4. Under **Environment Variables**, add:
   - `MONGODB_URI`: `<paste your actual MongoDB Atlas connection string>`
   - `PYTHON_VERSION`: `3.11.9`
5. Click **Create Web Service**.
6. Once deployed, copy your backend URL (e.g., `https://nexus-backend.onrender.com`).

#### 2. Deploy the Frontend Service
1. Click **New +** &rarr; **Web Service**.
2. Select your repository.
3. Configure the service:
   - **Name:** `nexus-frontend`
   - **Root Directory:** `frontend`
   - **Runtime:** `Node`
   - **Build Command:** `npm install && npm run build`
   - **Start Command:** `npm run start -- -p $PORT`
4. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL`: `https://nexus-backend.onrender.com` (using your backend URL from step 1)
   - `NODE_VERSION`: `20.14.0`
5. Click **Create Web Service**.

---

## Post-Deployment Verification

### 1. Verify Backend Liveness
```bash
curl https://<your-backend>.onrender.com/health
```
**Expected Output:**
```json
{"status":"ok"}
```

### 2. Verify Database Connection
```bash
curl https://<your-backend>.onrender.com/health/db
```
**Expected Output:**
```json
{"status":"ok","database":"connected"}
```

### 3. Verify Frontend UI
Open `https://<your-frontend>.onrender.com` in your browser. The status cards will display:
- **FastAPI Backend:** `Online` (`200 OK`)
- **MongoDB Atlas:** `Connected` (`200 OK`)
