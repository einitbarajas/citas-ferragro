# Resumen: Render OK + Vercel + rol Administrador de bodega

## 1. Render (API) — ya lo actualizaste

Comprueba: https://ferragro-api.onrender.com/health  

Debe verse `build_id` como `2026-05-22-prod-sync-v2` (o más reciente).

---

## 2. Vercel (portal) — pasos manuales

Ver archivo detallado: **`ACTUALIZAR-VERCEL.md`**

**Corto:**

1. https://vercel.com/ferragro/frontend → **Deployments** → **Redeploy** (Production).  
   **O** en PowerShell:

   ```powershell
   cd "c:\dev\trabajo ferragro\frontend"
   npx vercel deploy --prod --yes
   ```

2. Abre https://frontend-ferragro.vercel.app  
3. **Ctrl+F5** (muy importante: limpia caché del navegador).

---

## 3. Rol «Administrador de bodega» en el formulario Equipo

Ese rol **no es solo del front**: debe existir en PostgreSQL (tabla `Rol`).

Si el desplegable solo muestra Administrador / Logística (o Administrador duplicado):

```powershell
cd "c:\dev\trabajo ferragro"
$env:DATABASE_URL = "<External Database URL de Render ferragro-db>"
.\db\run-database-all.ps1
```

Luego **cerrar sesión** en el portal y volver a entrar → **Equipo** → debe aparecer **Administrador de bodega** y, al elegirlo, las **bodegas asignadas**.

---

## Orden recomendado

1. Render `/health` OK  
2. Migración BD (`020`) si falta el rol  
3. Redeploy Vercel + Ctrl+F5  
4. Probar Equipo → Administrador de bodega  
