#Requires -Version 5.1
<#
  Lista los secretos que deben existir en GitHub Actions para auto-deploy.
  Uso: .\scripts\setup-github-deploy-secrets.ps1
#>
Write-Host @"

GitHub → einitbarajas/citas-ferragro → Settings → Secrets and variables → Actions

| Secreto              | Donde obtenerlo |
|----------------------|-----------------|
| VERCEL_TOKEN         | https://vercel.com/account/tokens (Create Token) |
| RENDER_DEPLOY_HOOK   | Render → ferragro-api → Settings → Deploy Hook → Create Hook |

Workflows que los usan:
  .github/workflows/deploy-vercel-frontend.yml
  .github/workflows/deploy-render-api.yml

Vercel (opcional en panel en lugar de VERCEL_TOKEN):
  https://vercel.com/ferragro/frontend/settings/git
  Repo: einitbarajas/citas-ferragro | Branch: main | Root Directory: frontend

"@ -ForegroundColor Cyan

Start-Process "https://github.com/einitbarajas/citas-ferragro/settings/secrets/actions"
