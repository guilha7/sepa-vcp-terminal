# Publicar o Site Online 24/7 (100% Gratuito, Sem Cartão — Render + UptimeRobot)

Este guia mostra como colocar o **SEPA/VCP Trading Terminal** online num endereço próprio (`https://teu-terminal.onrender.com`) para acederes pelo **telemóvel ou qualquer computador**, com **HTTPS automático** e **proteção por password**, a **0€ e sem cartão de crédito**.

---

## Passo 1 — Enviar o Projeto Atualizado para o GitHub

Na pasta do projeto (`bot trading`), corre no terminal:

```powershell
git add .
git commit -m "Preparar deploy gratis Render + Multi-Estrategia"
git push
```

*(Confirma que `Dockerfile`, `render.yaml` e `.dockerignore` foram enviados para o teu repositório privado no GitHub.)*

---

## Passo 2 — Publicar Grátis no Render (Sem Cartão)

1. Cria conta gratuita em **[render.com](https://render.com)** (faz login com a tua conta **GitHub** — não pede cartão para o plano Free).
2. No painel do Render, clica em **New + → Web Service** (ou **Blueprint** para usar automaticamente o `render.yaml`).
3. Escolhe o teu repositório do GitHub (`sepa-vcp-terminal`).
4. Configura os campos (se usares Web Service manual):
   - **Name:** `sepa-vcp-desk` *(vai ficar `https://sepa-vcp-desk.onrender.com`)*
   - **Region:** `Frankfurt (EU Central)` *(mais rápido em Portugal!)*
   - **Language / Runtime:** `Docker`
   - **Instance Type:** **Free** (`$0/month`)
5. Em **Environment Variables** (muito importante — estas variáveis nunca se apagam entre deploys!), adiciona:
   - `APP_ACCESS_PASSWORD` = *(inventa uma password forte para só tu entrares no site!)*
   - `TELEGRAM_BOT_TOKEN` = *(o token do teu bot Telegram)*
   - `TELEGRAM_CHAT_ID` = *(o teu Chat ID do Telegram)*
   - `GEMINI_API_KEY` = *(opcional — a tua chave grátis do Google AI Studio)*
   - `DEFAULT_CAPITAL_EUR` = `100` *(ou o valor que quiseres)*
6. Clica em **Deploy Web Service**!
7. Passados **3 a 4 minutos**, o Render conclui o build e dá-te o link **HTTPS ao vivo** pronto a abrir no telemóvel!

*(Dica de telemóvel: no iPhone/Android, abre o link no Safari/Chrome e faz **"Adicionar ao Ecrã Principal"** — fica como uma app nativa!)*

---

## Passo 3 — Manter o Site Acordado 24/7 Grátis (UptimeRobot)

No plano gratuito do Render, o servidor entra em pausa se ficar 15 minutos sem visitas (e demora ~30s a acordar quando abres). Para evitar isso a **0€**:

1. Cria conta gratuita em **[uptimerobot.com](https://uptimerobot.com)** (sem cartão).
2. Clica em **Add New Monitor**:
   - **Monitor Type:** `HTTP(s)`
   - **Friendly Name:** `SEPA VCP Terminal`
   - **URL:** `https://TEU-NOME.onrender.com/api/health`
   - **Monitoring Interval:** `5 minutes`
3. Guarda! *(O endpoint `/api/health` responde `200 OK` mesmo quando o site está protegido com `APP_ACCESS_PASSWORD`, mantendo o servidor sempre acordado e rápido sem expor nenhum dado privado!)*

---

## Notas Importantes sobre o Plano Gratuito (Transparência Total)

- **Chaves & Configurações Permanentes:** Tudo o que colocares nas **Environment Variables** do Render (`APP_ACCESS_PASSWORD`, `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `DEFAULT_CAPITAL_EUR`) mantém-se para sempre mesmo quando fazes novos deploys.
- **Base de Dados SQLite no Render Free:** O disco local no plano Free do Render reinicia quando fazes um novo deploy. A cache de mercado volta a encher automaticamente em segundos, mas para o teu **histórico permanente de Paper Trading** continua a ser ótimo usar a versão local (`start.bat`) ou guardar o registo.
- **Alertas 24/7 à Prova de Falhas:** Mantém o **GitHub Actions** ([ALERTAS_CLOUD_GRATIS.md](file:///c:/Users/guilh/Desktop/bot%20trading/ALERTAS_CLOUD_GRATIS.md)) ativo em paralelo — assim recebes sempre o Briefing Matinal, Resumo de Domingo e Alertas de Preço mesmo que o Render reinicie!
