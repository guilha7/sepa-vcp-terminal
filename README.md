# SEPA/VCP Trading Terminal (Mark Minervini) — 100% Gratuito & Localhost

Aplicação web completa de apoio a trading para **Ações e Criptomoedas**, desenhada para correr localmente em `localhost` com **custo zero absoluto**, construída em torno da metodologia **SEPA / VCP de Mark Minervini**, rotação setorial de capital, sentimento de notícias, visão IA de gráficos e gestão de risco rígida (**Stop-Loss máximo de 6%**).

---

## Arquitetura & Stack Tecnológica

- **Backend:** Python + **FastAPI** + **SQLite** (cache TTL inteligente, watchlist, scans, alertas, paper trading e histórico de visão) + **APScheduler** (atualizações automáticas em background).
- **Frontend:** **React (Vite)** + **Tailwind CSS** (tema *dark terminal* profissional) + **TradingView Lightweight Charts**.
- **Fontes de Dados 100% Gratuitas:**
  - **Ações, ETFs, Índices Macro e Fundamentais:** `yfinance`.
  - **Criptomoedas:** `ccxt` (endpoints públicos da Binance sem API Key) com fallback automático para `yfinance` (`BTC-USD`, `ETH-USD`, `SOL-USD`, etc.).
  - **Notícias & Sentimento:** Feeds RSS gratuitos (Yahoo Finance RSS, Google News RSS, CoinDesk, Cointelegraph) + análise de sentimento local **VADER** com léxico financeiro ajustado.
  - **IA Modular (Briefings + Visão de Gráficos):** Suporta **Google Gemini API (Free Tier)** ou **Ollama Local** (`qwen2.5-vl` / `llama3.2-vision`), com fallback algorítmico limpo e transparente caso nenhum motor de IA esteja ativo.

---

## Os 5 Módulos do Dashboard

1. **Ambiente de Mercado & Rotação de Capital ("Onde está o dinheiro?"):**
   - **Semáforo Macro:** Classifica o mercado em *Risk-On* (Verde), *Cautela/Neutro* (Amarelo) ou *Risk-Off* (Vermelho) cruzando `SPY`, `QQQ`, `BTC-USD` face às SMAs 50 e 200, `^VIX`, `^TNX` (10Y Yield) e `DX-Y.NYB` (Dólar).
   - **Mapa de Rotação Setorial:** Performance e Força Relativa (1S, 1M, 3M) dos **11 ETFs setoriais EUA** (`XLK`, `XLF`, `XLV`, `XLE`, `XLY`, `XLP`, `XLI`, `XLB`, `XLU`, `XLRE`, `XLC`) e dos **principais setores Cripto**, destacando visualmente **Líderes (Inflow)** vs **Atrasados (Outflow)**.
2. **Scanner Automático Minervini (SEPA + VCP):**
   - Rastreia ações líquidas (S&P 500 / Nasdaq 100) e Top 30 criptomoedas (watchlist configurável na interface).
   - Aplica as **8 regras rígidas do Trend Template (Stage 2)**, deteta **contrações VCP por swings reais (ZigZag)**, sinal **"RS New High Before Price"**, **Volume Dry-Up (VDU)** junto ao pivô e **Breakouts válidos com volume >= 1.5x**.
   - **Modo Split-Screen + Navegação por Teclado (`↑`/`↓`/`Enter`)**: percorre os setups e vê imediatamente o gráfico candlestick + VCP + Linha RS à direita, com **barra de progresso em tempo real (SSE)** durante scans completos.
   - **Filtros Anti-Erro:** Ignora ativos sem liquidez mínima / penny stocks e destaca **alerta vermelho de Earnings nos próximos 14 dias**.
   - Inclui Score (0–100), Pivô, Stop-Loss <= 6%, Alvos 2R/3R, botão **"Alerta Pivô"** e cartão expansível **"Porque é que isto é uma oportunidade?"**.
3. **Raio-X Instantâneo de Ativo:**
   - Pesquisa global no topo e **Command Palette (`Ctrl+K`)** para saltar rapidamente para qualquer ticker ou módulo.
   - Gráfico candlestick interativo com alternância **Diário / Semanal**, SMA 50/150/200 (ou 10w/30w/40w), **Linha RS**, **contrações VCP desenhadas no gráfico**, Volume, Pivô e linha de Stop-Loss (-6%).
   - Checklist das 8 regras de Minervini com valores reais, fundamentais, notícias com sentimento VADER e **Briefing de Trader** gerado por IA.
4. **Analisador de Prints de Gráficos (Visão IA):**
   - Cola diretamente (`Ctrl+V`) ou arrasta screenshots de qualquer gráfico (TradingView, corretora) com ticker opcional para cruzamento automático com dados técnicos e notícias.
   - Devolve relatório estruturado: Tendência/Estrutura, Padrões/Níveis-Chave, Avaliação de Risco, Plano de Trade (Stop <= 6%) e Dica de Estudo.
5. **Gestão de Risco Rígida (6% Max Loss), FX EUR/USD & Diário Paper Trading:**
   - **Calculadora de Posição com Câmbio Live (`EURUSD=X`):** Capital predefinido em `100€` (editável), conversão automática USD↔EUR, stop padrão `6%` com **teto máximo absoluto de 7%**.
   - **Simulador Paper Trading Avançado:** Gestão ativa estilo Minervini com **parcial automática de 50% no alvo 2R + movimento automático de Stop para Breakeven (risco zero)**, opção de **Trailing Stop por SMA 10 / SMA 21**, curva de capital e **Diário de Trading** com estatísticas por Setup e Emoção.
6. **Central de Alertas & Notificações Gratuitas (Telegram / Discord):**
   - Alertas de preço customizados (ex: alerta no pivô), notificações automáticas de Breakouts VCP, mudanças no Semáforo Macro e Stops/2R no Paper Trading — diretamente no painel lateral ou enviados grátis para Telegram / Discord.
7. **Página de Definições (Settings) na Interface Web:**
   - Configura e testa a ligação à IA (Google Gemini Free Tier / Ollama local), ajusta o capital padrão e stop-loss, aplica pacotes temáticos do Scanner em 1 clique (*S&P/Nasdaq Líderes*, *Semicondutores & IA*, *High-Growth SEPA*, *11 ETFs Setoriais*, *Top 30 Cripto*), gere a cache SQLite e os intervalos do APScheduler sem editar `.env`.

---

## Requisitos Prévios

- **Python 3.11+** (testado em Python 3.13)
- **Node.js 18+** e `npm`

---

## Como Configurar e Correr em `localhost`

### Passo 1: Configurar `.env` (Opcional — já funciona 100% sem chaves!)

Copia `.env.example` para `.env` na raiz do projeto:

```bash
cp .env.example .env
```

#### Ativar IA Gratuita (Opcional):
- **Opção A — Google Gemini Free Tier (Recomendado para Visão IA):**
  1. Cria uma chave gratuita em [Google AI Studio](https://aistudio.google.com/apikey) (sem cartão de crédito).
  2. Define no `.env`:
     ```env
     AI_PROVIDER=auto
     GEMINI_API_KEY=a_tua_chave_aqui
     GEMINI_MODEL=gemini-2.5-flash
     ```
- **Opção B — Ollama 100% Local / Offline:**
  1. Instala o [Ollama](https://ollama.com) e descarrega um modelo de texto e visão:
     ```bash
     ollama pull llama3.2
     ollama pull qwen2.5-vl
     ```
  2. Garante que o Ollama está a correr em `http://127.0.0.1:11434`.

Se não configurares nenhuma opção, a aplicação funciona integralmente com **fallback algorítmico local limpo**.

---

### Passo 2: Arranque Rápido (1 Clique / 1 Comando)

- **Windows:** Faz duplo clique em `start.bat` (ou corre `.\start.bat` no terminal).
- **Linux / macOS:**
  ```bash
  chmod +x start.sh
  ./start.sh
  ```

O script cria automaticamente o ambiente virtual Python, instala dependências se necessário e abre:
- **Dashboard:** `http://127.0.0.1:5173`
- **Documentação API (Swagger):** `http://127.0.0.1:8000/docs`

---

### Arranque Manual (Desenvolvimento)

**Terminal 1 (Backend):**
```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate  |  Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm install
npm run dev
```

---

## Correr os Testes Automatizados

```bash
cd backend
.\.venv\Scripts\pytest -v tests/
```

---

## Cache & Rate-Limiting (SQLite)

| Categoria | TTL Predefinido | Objetivo |
|---|---|---|
| Preços OHLCV & Macro | 10 min (`600s`) | Evitar bloqueios do Yahoo Finance e acelerar carregamentos |
| Notícias RSS + VADER | 15 min (`900s`) | Atualização contínua sem abusar dos feeds |
| Scanner Completo SEPA/VCP | 6 horas (`21600s`) | Dashboard instantâneo + atualização periódica APScheduler |
| Fundamentais & Earnings | 24 horas (`86400s`) | Proteger chamadas `.info` / `.calendar` do Yahoo Finance |

> **Aviso Legal:** Esta ferramenta destina-se exclusivamente a estudo, análise quantitativa e simulação (*Paper Trading*). Não constitui aconselhamento financeiro.
