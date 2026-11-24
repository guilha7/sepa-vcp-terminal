# Guia do Utilizador — SEPA/VCP Trading Desk

Bem-vindo ao teu terminal pessoal de apoio a trading para **Ações e Criptomoedas**, 100% gratuito e desenhado em torno da metodologia **SEPA / VCP de Mark Minervini**, rotação de capital, análise de notícias, visão por IA e gestão de risco rígida (**perda máxima de 6%**).

Este guia explica **como usar o site na prática**, ecrã a ecrã, como se fosses um cliente a abrir a plataforma pela primeira vez.

---

## Como Abrir a Aplicação

1. Na pasta do projeto, faz **duplo clique em `start.bat`** (Windows) ou executa `./start.sh` (Mac/Linux).
2. Vão abrir-se duas janelas em segundo plano e o teu navegador abrirá automaticamente em:
   - **Endereço do site:** `http://127.0.0.1:5173`
3. Enquanto quiseres usar o site ou receber alertas no telemóvel, **mantém a janela do servidor aberta** (podes minimizá-la).

---

## Rotina Recomendada (5 Minutos por Dia)

Se quiseres tirar o máximo partido do terminal com disciplina, segue sempre esta ordem:

1. **Abre "Macro & Rotação"** → Vê a cor do Semáforo (Verde, Amarelo ou Vermelho) e descobre em que setores está a entrar dinheiro.
2. **Abre "Scanner SEPA / VCP"** → Filtra pelos melhores setups (`Stage 2 (8/8)` ou `VCP / Breakout`) e percorre os gráficos rapidamente com as setas **`↑` / `↓`** do teclado.
3. **Abre o "Raio-X"** do ativo que gostaste → Confirma o gráfico **Semanal + Diário**, verifica se não há **Earnings nos próximos 14 dias** e lê as notícias + Briefing de Trader.
4. **Define um Alerta ou Simula a Entrada** → Se ainda não rompeu o pivô, clica em **"Alerta Pivô"** para ser avisado no Telegram/Discord; se já está no ponto, clica em **"Simular Entrada"** para calcular a posição exata com stop máximo de **6%** e acompanhar no **Paper Trading**.

---

## Os 6 Ecrãs do Site (Explicação Completa)

### 1. Macro & Rotação (*"Onde está o dinheiro?"*)

Antes de comprar qualquer ação ou criptomoeda, este ecrã responde a duas perguntas essenciais: **"O mercado está favorável?"** e **"Que setores estão a liderar?"**.

- **Semáforo Macro (Topo):**
  - 🟢 **Risk-On (Verde):** Tendência de alta saudável nos índices (`SPY`, `QQQ`, `BTC`), volatilidade (`VIX`) calma e juros/dólar controlados. É o melhor ambiente para comprar breakouts.
  - 🟡 **Cautela / Neutro (Amarelo):** Sinais mistos. Sê muito seletivo, usa posições mais pequenas e realiza lucros parciais em 2R.
  - 🔴 **Risk-Off (Vermelho):** Mercado fraco ou em queda. A regra de ouro de Minervini é proteger o capital: evita novas compras agressivas e aguarda melhoria.
- **Cartões de Indicadores Macro:** Mostra `SPY`, `QQQ`, `BTC-USD`, `^VIX` (medo do mercado), `^TNX` (juros a 10 anos) e `DXY` (dólar), indicando se cada um está acima ou abaixo das médias de 50 e 200 dias. Clicar em `SPY`, `QQQ` ou `BTC-USD` abre logo o seu Raio-X.
- **Mapa de Rotação Setorial:**
  - Podes alternar entre **11 Setores EUA (ETFs)** e **Setores Cripto**, e escolher o período (**1 Semana**, **1 Mês**, **3 Meses**).
  - **Onde o capital está a entrar (Líderes — Verde):** Setores com maior Força Relativa — é aqui que deves procurar compras.
  - **De onde o capital está a sair (Atrasados — Vermelho):** Setores fracos — evita comprar contra a corrente.
  - Clicar em qualquer ETF setorial (ex: `XLK`, `XLE`, `XLP`) abre logo o gráfico completo no Raio-X.

---

### 2. Scanner Automático Minervini (SEPA + VCP)

Este é o radar automático que analisa dezenas de ações líquidas e as Top 30 criptomoedas para encontrar as melhores oportunidades de tendência e contração de volatilidade.

- **Modo Split-Screen + Teclado (Super Rápido):**
  - À esquerda tens a lista ordenada por **Score (0 a 100)**.
  - À direita vês imediatamente o **gráfico candlestick** do ativo selecionado, com as médias móveis, linha RS, contrações VCP, linha de Pivô e linha de Stop (-6%).
  - **Dica de produtividade:** usa as setas **`↑`** e **`↓`** do teclado para percorrer a lista e rever 20 gráficos em 1 minuto. Prime **`Enter`** para abrir o Raio-X completo do ativo selecionado.
- **O que significam as etiquetas (Badges):**
  - `BREAKOUT VCP`: O ativo rompeu o pivô de resistência com volume forte (≥ 1.5x acima da média).
  - `VCP PRONTO (VDU)`: A volatilidade apertou (`T1 → T2 → T3`) e o volume "secou" (*Volume Dry-Up*) junto à resistência — ponto ideal para colocar um **Alerta Pivô**.
  - `STAGE 2 (8/8)`: Cumpre todas as 8 regras rígidas de tendência de Mark Minervini.
  - `● RS NEW HIGH`: A Força Relativa atingiu novo máximo de 52 semanas **antes** do preço — um forte sinal de acumulação institucional.
  - 🔴 `EARNINGS EM X DIAS`: **Alerta vermelho crítico!** A empresa vai apresentar resultados nos próximos 14 dias. Evita abrir posições novas antes de resultados devido ao risco de *gap* noturno acima do stop de 6%.
- **"Porque é que isto é uma oportunidade?":** Explica em linguagem simples porque é que o ativo teve aquela pontuação, destacando pontos fortes e avisos de risco.
- **Novo Scan Completo:** Clica no botão verde no topo direito para atualizar todo o mercado — vais ver uma **barra de progresso em tempo real** a indicar qual o ativo a ser analisado.
- **Botão Watchlist:** Permite adicionar ou remover tickers personalizados (ex: `RKLB`, `HIMS`, `SOL-USD`) sempre que quiseres.

---

### 3. Raio-X Instantâneo de Ativo

Podes abrir o Raio-X clicando em qualquer ativo no site, escrevendo na **barra de pesquisa no topo** ou carregando em **`Ctrl+K`**.

- **Gráfico Interativo (Diário & Semanal):**
  - Alterna entre **Diário** (`SMA 50`, `150`, `200`) e **Semanal** (`SMA 10w`, `30w`, `40w`) para ver a tendência grande antes de afinar o ponto de entrada.
  - Podes ligar/desligar a **Linha RS** (força relativa a azul), as **Contrações VCP (`T1`, `T2`, `T3`)** desenhadas no gráfico e as linhas de **Pivô** (verde) e **Stop -6%** (vermelho).
  - Usa o rato para fazer zoom, arrastar datas e inspecionar valores exatos.
- **Checklist das 8 Regras de Minervini:** Mostra cada uma das 8 regras com `PASSOU` (verde) ou `FALHOU` (vermelho) e os números reais do ativo.
- **Diagnóstico VCP & Plano de Risco:** Sugere automaticamente um preço de Pivô, Stop Técnico (nunca superior a 6%) e alvos **2R** e **3R**.
- **Fundamentais & Earnings:** Mostra capitalização, crescimento de receitas e lucros, P/E, margem, ROE e próxima data de resultados.
- **Notícias & Sentimento:** Recolhe as últimas manchetes gratuitas e classifica cada notícia automaticamente em **Positivo**, **Neutro** ou **Negativo**.
- **Briefing de Trader (IA):** Resume os **Catalisadores Atuais**, os **Principais Riscos** e um **Veredito Objetivo**. *(Funciona com Gemini grátis, Ollama local ou análise algorítmica local caso não tenhas IA externa configurada.)*
- **Botões rápidos no topo:** **"Alerta Pivô"** (cria alerta de preço) e **"Simular Entrada"** (envia o ativo diretamente para a Calculadora e Paper Trading).

---

### 4. Visão IA Gráficos (Analisar Prints)

Viste um gráfico interessante no TradingView ou na tua corretora e queres uma segunda opinião estruturada?

1. Tira um print ao gráfico e carrega simplesmente **`Ctrl+V`** nesta página (ou arrasta a imagem / clica em *Escolher Ficheiro*).
2. *(Opcional, mas recomendado)* Escreve o **Ticker** (ex: `NVDA`, `SOL-USD`), o **Timeframe** e qualquer dúvida que tenhas. Se indicares o ticker, o site cruza o print com dados reais e notícias do momento.
3. Clica em **"Analisar Gráfico com Visão IA"**.
4. Recebes um relatório dividido em 5 blocos:
   1. **Tendência e Estrutura**
   2. **Padrões e Níveis-Chave (Suporte / Resistência)**
   3. **Avaliação de Risco** (alerta para possíveis *fakeouts* ou preços esticados)
   4. **Sugestão de Plano** (entrada, stop rigorosamente ≤ 6% e alvos 2R/3R)
   5. **Dica de Estudo** (o que deves treinar o olho a observar naquele gráfico)
5. As tuas análises ficam guardadas no **Histórico Recente** em baixo para consultares mais tarde.

*(Dica: Para leitura visual avançada dos candles por IA, configura gratuitamente uma chave do Google Gemini ou o Ollama local na página **Definições**.)*

---

### 5. Risco 6% & Paper Trading + Diário

Este módulo protege o teu capital contra grandes perdas e permite treinar sem arriscar dinheiro real.

#### Calculadora Automática de Posição (com Câmbio EUR/USD ao vivo)
- Introduzes o teu **Capital em Euros** (predefinido em `100€`, editável), o **Preço de Entrada** e a **Moeda do Ativo** (`USD` ou `EUR`).
- O site busca automaticamente a taxa de câmbio **`EUR/USD`** para calcular exatamente **quantas ações ou moedas comprar**, qual o **Preço de Stop-Loss**, a **Perda Máxima real em Euros** e quanto ganhas nos alvos **2R** e **3R**.
- **Proteção Rígida de Stop-Loss:** O padrão é **6%**. Entre 6.1% e 7% o site mostra um aviso amarelo, e **bloqueia totalmente qualquer stop acima de 7%** para proteger a tua conta.

#### Simulador de Paper Trading (Gestão Ativa estilo Minervini)
Ao clicar em **"Simular Entrada"**, podes ativar proteções automáticas:
- **Auto 2R (Vender 50% + Breakeven):** Quando o ativo atingir `+2R` de lucro, o simulador vende automaticamente metade para garantir lucro e sobe o stop-loss do resto para o preço de entrada (**risco zero / Breakeven**).
- **Trailing Stop (SMA 10 / SMA 21):** Sobe automaticamente o stop à medida que o ativo sobe, acompanhando a média móvel de 10 ou 21 dias.
- **Stop-Loss Automático:** Se o preço cair abaixo do teu Stop, a posição é fechada automaticamente e recebes um alerta.
- **Botão Cadeado (`🔒`):** Permite mover manualmente o stop de uma posição aberta para Breakeven com 1 clique.

#### Diário de Trading (*Onde Ganhas vs. Onde Perdes*)
- Em cada trade escolhes a etiqueta de **Setup** (`VCP`, `BREAKOUT`, `FOMO`, etc.) e a tua **Emoção** (`DISCIPLINADO`, `ANSIOSO`, `FOMO`, etc.), e podes clicar no ícone de caderno (`📝`) para escrever a tua **lição pós-trade**.
- À medida que fechas trades, o painel gera automaticamente o teu **Win Rate**, **Profit Factor**, **Max Drawdown**, **Curva de Capital** e a tabela comparativa de **quanto dinheiro ganhas ou perdes em cada tipo de Setup e Emoção**.

---

### 6. Central de Alertas (Sino no Topo Direito)

Clicando no botão **Alertas** (topo direito), abre-se o painel lateral com 3 separadores:
1. **Feed:** Histórico de todos os alertas (Breakouts VCP detetados, Mudanças no Semáforo Macro, Alvos 2R, Stops automáticos e Alertas de preço).
2. **Alertas de Preço:** Cria alertas personalizados como *"Avisar quando SPOT cruzar acima de 520"* e clica em **"Verificar Agora"** quando quiseres testar de imediato.
3. **Telegram / Discord (Grátis):** Cola o teu Token + Chat ID do Telegram ou URL de Webhook do Discord e clica em **"Testar"** para receberes alertas diretamente no telemóvel.

> **Importante — Os alertas funcionam com o computador desligado?**
> **Não.** Como o terminal é 100% gratuito e corre localmente no teu computador (sem servidores pagos na nuvem), o servidor precisa de estar a correr para verificar os preços e enviar mensagens para o Telegram/Discord.
> - **Browser fechado + janela do servidor aberta/minimizada:** ✅ **Funciona!** Continuas a receber alertas no telemóvel.
> - **Servidor fechado ou PC desligado/em suspensão:** ❌ **Não envia alertas** enquanto estiver desligado. Assim que voltares a abrir o `start.bat`, ele verifica os preços atuais e dispara os alertas que tenham atingido o alvo.

---

### 7. Definições (Personalizar Tudo sem Mexer em Código)

Na aba **Definições** (último item do menu lateral) controlas tudo visualmente:
- **Motor de IA:** Cola a tua chave gratuita do **Google Gemini** (ou aponta para o **Ollama** local) e clica em **"Testar Ligação IA"** para confirmar em segundos se está operacional.
- **Perfil de Risco:** Altera o teu capital base padrão (ex: de `100€` para `250€`) e o stop padrão (ex: `5%`) — atualiza imediatamente a Calculadora e o Paper Trading.
- **Pacotes de Universo do Scanner (1-Clique):** Adiciona ou troca listas inteiras de ativos (*S&P/Nasdaq Líderes*, *Semicondutores & IA*, *High-Growth SEPA*, *11 ETFs Setoriais*, *Top 30 Cripto*) sem adicionar ticker a ticker.
- **Cache & Agendador:** Vê o tamanho da base de dados, limpa a cache com 1 clique se quiseres forçar dados novos e escolhe de quantos em quantos minutos o terminal atualiza preços, alertas e scans automaticamente.

---

## Atalhos de Teclado Úteis

| Atalho | Onde funciona | O que faz |
|---|---|---|
| **`Ctrl + K`** | Em qualquer ecrã | Abre a pesquisa rápida para saltar para qualquer ação, cripto, módulo ou alertas |
| **`↑` / `↓`** | No Scanner (Split-Screen) | Percorre os setups e troca o gráfico à direita instantaneamente |
| **`Enter`** | No Scanner (Split-Screen) | Abre o Raio-X completo do ativo selecionado |
| **`Ctrl + V`** | Em "Visão IA Gráficos" | Cola diretamente um print de gráfico copiado para a área de transferência |

---

## Perguntas Frequentes

- **Tenho de pagar alguma coisa ou pôr cartão de crédito?**
  Não. Todos os dados de mercado, notícias, sentimento, alertas Telegram/Discord e até o plano gratuito do Google Gemini ou Ollama local têm custo zero.
- **Se fechar o site perco os meus trades do Paper Trading ou as minhas definições?**
  Não. Tudo (posições, diário, watchlist, alertas, histórico de prints e definições) fica guardado localmente no teu computador numa base de dados SQLite.
- **Porque é que às vezes aparece um aviso amarelo discreto no topo?**
  É o modo tolerante a falhas: se alguma fonte gratuita (ex: um feed de notícias ou um dado fundamental de um ETF) falhar momentaneamente, o site nunca crasha — mostra tudo o que conseguiu obter e avisa discretamente o que faltou.

> *Aviso: Esta ferramenta destina-se exclusivamente a apoio à decisão, estudo da metodologia SEPA/VCP e simulação (Paper Trading). Não constitui aconselhamento financeiro.*
