# Alertas 24/7 com o PC Desligado (100% Gratuito via GitHub Actions)

Este guia mostra como ativar o **Monitor na Nuvem** em cerca de **2 minutos**, totalmente gratuito e **sem cartão de crédito**, para receberes alertas no **Telegram** ou **Discord** mesmo com o teu computador desligado.

---

## O que este monitor vigia automaticamente na nuvem?

- **A cada 30 minutos (Seg–Sex, 13h–21h UTC — sessão da bolsa EUA):** verifica todos os teus **Alertas de Preço** (`alertas_cloud.json`) e mudanças no **Semáforo Macro** (*Risk-Off → Cautela → Risk-On*).
- **A cada 4 horas (24/7 — inclui fins de semana para Cripto):** corre o **Scanner SEPA/VCP** completo e envia alerta se encontrar um **Breakout VCP** (volume ≥ 1.5x) ou **VCP Pronto (VDU)** com Score elevado.
- **Anti-Spam automático:** o ficheiro `cloud_state.json` é atualizado automaticamente pelo próprio GitHub para nunca te mandar o mesmo alerta repetido.
- **Custo:** **0€** (gasta ~150–250 min/mês num limite gratuito de **2.000 minutos/mês** do GitHub para repositórios privados).

---

## Passo a Passo para Ativar (2 Minutos)

### Passo 1 — Criar um Repositório Privado Grátis no GitHub
1. Entra em [github.com](https://github.com) (cria conta grátis se ainda não tiveres).
2. Clica no botão verde **New** (Novo Repositório).
3. Dá um nome, por exemplo: `sepa-vcp-terminal`.
4. Escolhe **Private** (Privado) e clica em **Create repository**.

### Passo 2 — Enviar esta pasta para o teu GitHub
Abre o terminal (PowerShell) na pasta do projeto (`bot trading`) e executa:

```powershell
git init
git add .
git commit -m "Inicializar SEPA/VCP Trading Terminal + Cloud Alerts"
git branch -M main
git remote add origin https://github.com/TEU_UTILIZADOR/sepa-vcp-terminal.git
git push -u origin main
```

*(Nota: o ficheiro `.env` e a tua base local `.db` estão no `.gitignore`, por isso as tuas chaves locais nunca são expostas.)*

### Passo 3 — Adicionar o Token do Telegram (ou Discord) nos Secrets do GitHub
1. No teu repositório no GitHub, vai ao separador **Settings** (Definições).
2. No menu esquerdo clica em **Secrets and variables → Actions**.
3. Clica em **New repository secret** e adiciona:
   - Nome: `TELEGRAM_BOT_TOKEN` → Valor: o token que o `@BotFather` te deu
   - Nome: `TELEGRAM_CHAT_ID` → Valor: o teu número de ID do `@userinfobot`
   - *(Opcional se usares Discord)* Nome: `DISCORD_WEBHOOK_URL` → Valor: o URL do webhook

### Passo 4 — Ativar Permissão de Escrita (para o Anti-Spam funcionar)
1. Ainda em **Settings → Actions → General** (menu esquerdo).
2. Desce até **Workflow permissions**.
3. Seleciona **Read and write permissions** e clica em **Save**.

### Passo 5 — Fazer o Primeiro Teste Agora Mesmo!
1. Vai ao separador **Actions** no topo do teu repositório no GitHub.
2. Clica em **SEPA/VCP Alertas Cloud 24/7** no lado esquerdo.
3. Clica em **Run workflow** (botão à direita):
   - Marca a caixinha **"Enviar mensagem de teste no Telegram/Discord"** (`true`).
   - Clica em **Run workflow**.
4. Passados ~30 segundos vais receber uma mensagem no **Telegram** vinda diretamente da nuvem do GitHub — **pronto, está a funcionar 24/7!**

---

## Como Adicionar ou Alterar Alertas de Preço

Tens duas formas super fáceis:

### Forma A — Diretamente pelo Telemóvel (App ou site do GitHub)
1. Abre o ficheiro **`alertas_cloud.json`** no teu repositório no GitHub e clica no lápis (**Edit**).
2. Adiciona os teus alertas de preço dentro de `"price_alerts"`:
   ```json
   {
     "id": "spot-pivo",
     "ticker": "SPOT",
     "condition": "ABOVE",
     "target_price": 520.0,
     "notes": "Rompimento do pivô VCP",
     "enabled": true
   }
   ```
   - `condition`: usa `"ABOVE"` (avisar quando subir acima do preço) ou `"BELOW"` (avisar quando cair abaixo).
3. Clica em **Commit changes** — na verificação seguinte o GitHub já vigia o novo alerta!

### Forma B — Com 1 Clique no Site Local
1. No dashboard (`http://127.0.0.1:5173`), cria os teus alertas de preço normalmente (ou usa o botão **"Alerta Pivô"** no Scanner/Raio-X).
2. Abre **Alertas** → aba **Alertas de Preço** → clica em **"Exportar p/ Cloud"** (atualiza logo o ficheiro `alertas_cloud.json`).
3. Envia a atualização para o GitHub:
   ```powershell
   git add alertas_cloud.json
   git commit -m "Atualizar alertas de preço"
   git push
   ```
