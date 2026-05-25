# Desplegar la versión nueva (2 minutos)

## Opción rápida (script)

```powershell
cd "c:\dev\trabajo ferragro"
.\scripts\desplegar-produccion.ps1
```

Pega la **Deploy Hook URL** de Render cuando lo pida (solo la primera vez).

## Manual (si no tienes el hook)

### 1. Render (API)

1. https://dashboard.render.com/web/srv-d82dvanaqgkc739362u0  
2. **Manual Deploy** → **Deploy latest commit**  
3. Espera **Live**  
4. https://ferragro-api.onrender.com/health → `build_id`: **2026-05-25-prod-v1**

### 2. Vercel (portal)

1. https://vercel.com/ferragro/frontend/deployments  
2. **Redeploy** (Production)  
3. https://frontend-ferragro.vercel.app → **Ctrl+F5**

## Automático en cada push (una vez)

GitHub → repo → **Settings** → **Secrets** → **Actions**:

| Secreto | Dónde |
|---------|--------|
| `RENDER_DEPLOY_HOOK` | Render → ferragro-api → Deploy Hook |
| `VERCEL_TOKEN` | https://vercel.com/account/tokens |

O conecta el repo en Vercel (**Settings → Git**, root `frontend`).
