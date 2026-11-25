# Publicar o Site Online 24/7 para Ti e os Teus Amigos (100% Grátis — Render)

Este guia coloca o **SEPA/VCP Trading Terminal** online num endereço HTTPS próprio (`https://teu-terminal.onrender.com`) a **0€ e sem cartão de crédito**, pronto a partilhar com amigos!

### Como funciona para os teus amigos
- **Zero password para entrar:** basta enviar o link — eles escrevem apenas o **nome deles** (ex: `João`, `Diogo`) e entram imediatamente.
- **Paper Trading & Diário individuais:** cada amigo vê apenas as suas próprias simulações, Win Rate e SQN (não misturam nem apagam trades uns dos outros).
- **Segurança só para ti (`ADMIN_PASSWORD`):** a aba **Definições** (chave Gemini, cache, pacotes) e os **canais do teu Telegram/Discord** ficam trancados — só tu consegues mexer com a tua `ADMIN_PASSWORD`.

---

## Passo 1 — Enviar o Projeto Atualizado para o GitHub

Na pasta do projeto (`bot trading`), corre:

```powershell
git add .
git commit -m "Modo Amigos + Deploy Gratis Render"
git push
```

---

## Passo 2 — Publicar Grátis no Render (Sem Cartão)

1. Cria conta gratuita em **[render.com](https://render.com)** entrando com o teu **GitHub**.
2. Clica em **New + → Web Service** (ou **Blueprint** para ler o `render.yaml`).
3. Escolhe o teu repositório do GitHub.
4. Confirma as definições:
   - **Region:** `Frankfurt (EU Central)`
   - **Language / Runtime:** `Docker`
   - **Instance Type:** **Free** (`$0/month`)
5. Em **Environment Variables**, adiciona:
   - `ADMIN_PASSWORD` = *(password só para ti — protege Definições e o teu Telegram dos amigos!)*
   - `TELEGRAM_BOT_TOKEN` = *(o token do teu bot Telegram)*
   - `TELEGRAM_CHAT_ID` = *(o teu Chat ID do Telegram)*
   - `GEMINI_API_KEY` = *(opcional — chave grátis do Google AI Studio)*
   - `DEFAULT_CAPITAL_EUR` = `100`
   - *(Não adiciones `APP_ACCESS_PASSWORD` — assim os teus amigos entram só com o nome!)*
6. Clica em **Deploy Web Service** e aguarda 3–4 minutos.
7. Partilha o link `https://...onrender.com` com os teus amigos!

---

## Passo 3 — Manter o Site Acordado 24/7 Grátis (UptimeRobot)

Para evitar que o plano Free do Render adormeça ao fim de 15 minutos sem visitas:
1. Cria conta grátis em **[uptimerobot.com](https://uptimerobot.com)** (sem cartão).
2. **Add New Monitor → HTTP(s):**
   - **URL:** `https://TEU-NOME.onrender.com/api/health`
   - **Interval:** `5 minutes`
3. Guarda! Assim o site responde rápido 24/7.

> **Nota sobre SQLite no Render Free:** as variáveis de ambiente (`ADMIN_PASSWORD`, `TELEGRAM_*`, `GEMINI_API_KEY`) são permanentes, mas o disco local do plano Free reinicia quando fazes novos deploys. Para alertas 24/7 garantidos mesmo durante reinícios, mantém o **GitHub Actions** ([ALERTAS_CLOUD_GRATIS.md](file:///c:/Users/guilh/Desktop/bot%20trading/ALERTAS_CLOUD_GRATIS.md)) ativo em paralelo.
