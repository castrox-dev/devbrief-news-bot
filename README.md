# DevBrief News

Bot em Python que gera automaticamente um resumo das principais notícias das últimas 24 horas utilizando a **API NVIDIA NIM** (modelo DeepSeek) e envia o resultado para **Telegram** e **e-mail** todos os dias às **07:00** (fuso `America/Sao_Paulo`).

A identidade visual usa a logo em `assets/logo.png` no template de e-mail.

## Funcionalidades

- Agendamento diário com **APScheduler** (local) ou **Vercel Cron** (nuvem)
- **Alertas urgentes** de breaking news a cada 30 minutos (mercado, tech, geopolítica)
- Geração de resumo via **NVIDIA NIM API** (compatível com SDK OpenAI) com retry automático
- **Mercado financeiro**: feeds dedicados + cotações (dólar, euro, bitcoin) no briefing
- Envio ao **Telegram** com divisão automática de mensagens longas
- Envio por **e-mail HTML** via [Resend](https://resend.com/) com template responsivo
- Logging completo em `logs/bot.log`
- Execução imediata com `--run-now` e `--breaking-now` para testes
- Preview do e-mail com `--preview-email`

## Requisitos

- Python 3.12 ou superior
- Chave de API na [NVIDIA Build](https://build.nvidia.com/)
- Bot do Telegram criado via [@BotFather](https://t.me/BotFather)

## Instalação

```powershell
cd daily-news-bot
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuração

1. Copie o arquivo de exemplo:

```powershell
copy .env.example .env
```

2. Edite o `.env` e preencha as variáveis:

```env
AI_API_KEY=sua_chave_nvidia_nvapi
AI_BASE_URL=https://integrate.api.nvidia.com/v1
AI_MODEL=deepseek-ai/deepseek-v4-pro
TELEGRAM_BOT_TOKEN=seu_token_do_bot
TELEGRAM_CHAT_ID=id_do_chat_ou_grupo
```

### Como obter a AI_API_KEY (NVIDIA)

1. Acesse [https://build.nvidia.com/](https://build.nvidia.com/) e faça login
2. Vá em **Settings** → **API Keys** (ou acesse um modelo como o DeepSeek)
3. Gere uma chave no formato `nvapi-...`
4. Cole em `AI_API_KEY` no arquivo `.env`

> **Importante:** nunca compartilhe ou versione sua chave de API.

> **Limitação:** o modelo gera o resumo com base no conhecimento do LLM, não navega na web em tempo real. Para notícias 100% atualizadas de fontes reais, seria necessário integrar uma API de notícias (ex.: NewsAPI, RSS feeds) e enviar os artigos ao modelo para resumir.

### Como criar o Bot no Telegram

1. Abra o Telegram e busque [@BotFather](https://t.me/BotFather)
2. Envie o comando `/newbot`
3. Escolha um nome e um username (deve terminar em `bot`)
4. O BotFather retornará o **token** — cole em `TELEGRAM_BOT_TOKEN`

### Como obter o CHAT_ID

**Para conversa privada:**

1. Envie qualquer mensagem para o seu bot
2. Acesse no navegador:

```
https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
```

3. Procure o campo `"chat":{"id":123456789}` — esse número é o `TELEGRAM_CHAT_ID`

**Para grupos:**

1. Adicione o bot ao grupo
2. Envie uma mensagem no grupo (ex.: `/start`)
3. Acesse a mesma URL `getUpdates` acima
4. O `chat.id` de grupos/supergrupos geralmente é negativo (ex.: `-1001505106488`)

> Se o ID do grupo for `1505106488`, o formato de supergrupo costuma ser `-1001505106488`.

### Como configurar o E-mail (Resend)

1. Crie uma conta em [https://resend.com/](https://resend.com/)
2. Gere uma API Key em **API Keys** (formato `re_...`)
3. Configure no `.env`:

```env
RESEND_API_KEY=re_sua_chave
EMAIL_FROM=Daily News Bot <onboarding@resend.dev>
EMAIL_TO=seu-email@gmail.com
```

4. Para produção, verifique seu domínio no Resend e use um remetente do seu domínio (ex.: `news@seudominio.com`)
5. Múltiplos destinatários: `EMAIL_TO=email1@x.com,email2@x.com`

O template HTML está em `templates/email_template.html` e é compatível com:
- Gmail (Android, iOS, Web)
- Outlook (Windows, Mac, Web)
- Apple Mail (macOS, iOS)
- Yahoo Mail, Thunderbird e demais clientes

**Compatibilidade do template:**
- Layout em tabelas (padrão ouro para e-mail)
- CSS inline + bloco `<style>` com fallback
- Sem JavaScript (bloqueado em todos os clientes)
- Animações CSS degradam graciosamente para layout estático no Outlook/Gmail
- Gradientes com fallback de cor sólida + VML para Outlook
- Responsivo via `@media` para mobile (Android/iOS)

### Preview do e-mail (sem enviar)

```powershell
python main.py --preview-email
```

Abra `logs/email_preview.html` no navegador para visualizar o template.

## Como executar

### Modo agendado (padrão — local)

Inicia o scheduler, executa o briefing às 07:00 e monitora breaking news a cada 30 min:

```powershell
python main.py
```

### Execução imediata (teste)

```powershell
python main.py --run-now
python main.py --breaking-now
```

Os logs são gravados em `logs/bot.log`.

## Deploy na Vercel (recomendado para hospedagem)

O bot foi adaptado para rodar na Vercel com dois cron jobs:

| Job | Horário | Endpoint |
|-----|---------|----------|
| Briefing diário | 07:00 (Brasília) | `/api/cron/daily` |
| Breaking news | A cada 30 min | `/api/cron/breaking` |

### 1. Pré-requisitos

- Conta na [Vercel](https://vercel.com/)
- **Plano Pro** recomendado (cron a cada 30 min exige Pro; o briefing diário funciona no Hobby)
- [Upstash Redis](https://upstash.com/) gratuito (evita reenviar alertas duplicados)

### 2. Deploy

```powershell
npm i -g vercel
vercel login
vercel
```

### 3. Variáveis de ambiente na Vercel

No painel **Settings → Environment Variables**, configure:

| Variável | Obrigatória |
|----------|-------------|
| `AI_API_KEY` | Sim |
| `TELEGRAM_BOT_TOKEN` | Sim |
| `TELEGRAM_CHAT_ID` | Sim |
| `CRON_SECRET` | Sim (gere com `openssl rand -hex 32`) |
| `UPSTASH_REDIS_REST_URL` | Recomendado |
| `UPSTASH_REDIS_REST_TOKEN` | Recomendado |
| `RESEND_API_KEY` | Opcional |
| `EMAIL_FROM` / `EMAIL_TO` | Opcional |

### 4. Testar após deploy

```text
GET https://seu-projeto.vercel.app/api/health
GET https://seu-projeto.vercel.app/api/cron/daily
  Header: Authorization: Bearer SEU_CRON_SECRET
```

### 5. Como funciona o monitoramento contínuo

Na Vercel não existe processo 24/7. O bot simula isso com:

1. **Cron a cada 30 min** — busca notícias das últimas 3h, pontua por impacto (Selic, dólar, crash, guerra, etc.) e a IA confirma se vale alerta
2. **Cron diário às 07h** — briefing completo com mercado financeiro e cotações

### Plano Hobby vs Pro

- **Hobby**: apenas 1 cron por dia → briefing diário funciona; breaking news precisa de serviço externo (ex.: [cron-job.org](https://cron-job.org)) chamando `/api/cron/breaking` a cada 30 min
- **Pro**: ambos os crons funcionam nativamente

## Estrutura do projeto

```
daily-news-bot/
├── main.py
├── news_prompt.txt
├── breaking_prompt.txt
├── vercel.json
├── requirements.txt
├── .env.example
├── README.md
├── api/
│   ├── cron/
│   │   ├── daily.py
│   │   └── breaking.py
│   └── health.py
├── services/
│   ├── jobs.py
│   ├── breaking_detector.py
│   ├── alert_store.py
│   ├── market_data.py
│   ├── news_fetcher.py
│   ├── openai_service.py
│   ├── telegram_service.py
│   ├── email_service.py
│   └── email_renderer.py
├── templates/
│   └── email_template.html
├── scheduler/
│   └── scheduler.py
└── logs/
    └── bot.log
```

## Personalização

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `AI_BASE_URL` | `https://integrate.api.nvidia.com/v1` | URL da API NVIDIA NIM |
| `AI_MODEL` | `deepseek-ai/deepseek-v4-pro` | Modelo utilizado |
| `AI_TEMPERATURE` | `1` | Temperatura da geração |
| `AI_TOP_P` | `0.95` | Parâmetro top_p |
| `AI_MAX_TOKENS` | `8192` | Máximo de tokens na resposta |
| `TIMEZONE` | `America/Sao_Paulo` | Fuso horário do agendamento |
| `SCHEDULE_TIME` | `07:00` | Horário diário de execução |
| `BREAKING_MIN_SCORE` | `5` | Sensibilidade dos alertas urgentes |
| `BREAKING_MAX_AGE_HOURS` | `3` | Janela de horas para breaking news |
| `CRON_SECRET` | — | Proteção dos endpoints na Vercel |

O prompt pode ser editado em `news_prompt.txt`.

## Instalar como serviço do Windows (NSSM)

O [NSSM](https://nssm.cc/) (Non-Sucking Service Manager) permite rodar o bot como serviço Windows.

1. Baixe o NSSM e extraia em `C:\nssm`
2. Instale o serviço (execute como Administrador):

```powershell
C:\nssm\nssm.exe install DailyNewsBot "C:\caminho\para\daily-news-bot\venv\Scripts\python.exe" "C:\caminho\para\daily-news-bot\main.py"
```

3. Configure o diretório de trabalho:

```powershell
C:\nssm\nssm.exe set DailyNewsBot AppDirectory "C:\caminho\para\daily-news-bot"
```

4. Inicie o serviço:

```powershell
C:\nssm\nssm.exe start DailyNewsBot
```

5. Para parar ou remover:

```powershell
C:\nssm\nssm.exe stop DailyNewsBot
C:\nssm\nssm.exe remove DailyNewsBot confirm
```

## Agendar no Windows Task Scheduler

Alternativa sem NSSM — executar o job uma vez por dia:

1. Abra **Agendador de Tarefas** (`taskschd.msc`)
2. **Criar Tarefa Básica**
3. Nome: `Daily News Bot`
4. Disparador: **Diariamente**, às **07:00**
5. Ação: **Iniciar um programa**
6. Programa:

```
C:\caminho\para\daily-news-bot\venv\Scripts\python.exe
```

7. Argumentos:

```
C:\caminho\para\daily-news-bot\main.py --run-now
```

8. Iniciar em:

```
C:\caminho\para\daily-news-bot
```

> Use `--run-now` no Task Scheduler para executar uma vez e encerrar. Use `main.py` sem argumentos se preferir um processo contínuo com APScheduler interno.

## Empacotar com PyInstaller (.exe)

Gere um executável Windows standalone:

### 1. Instalar PyInstaller

```powershell
pip install pyinstaller
```

### 2. Gerar o executável

Na pasta do projeto:

```powershell
pyinstaller --onefile --name DailyNewsBot --add-data "news_prompt.txt;." --hidden-import=tzdata main.py
```

> No Windows, separe arquivos adicionais com `;` em `--add-data`.

### 3. Copiar arquivos necessários

O `.exe` ficará em `dist\DailyNewsBot.exe`. Copie para uma pasta de deploy:

```
deploy/
├── DailyNewsBot.exe
├── .env
├── news_prompt.txt
└── logs/
```

### 4. Executar o .exe

```powershell
.\DailyNewsBot.exe
```

Para teste imediato:

```powershell
.\DailyNewsBot.exe --run-now
```

### 5. Script de build (opcional)

Crie `build.bat`:

```bat
@echo off
pyinstaller --onefile --name DailyNewsBot --add-data "news_prompt.txt;." --hidden-import=tzdata main.py
echo Build concluido em dist\DailyNewsBot.exe
pause
```

### Observações do PyInstaller

- O arquivo `.env` **não** é embutido no `.exe` por segurança — mantenha-o ao lado do executável
- Crie a pasta `logs/` manualmente ou ela será criada automaticamente na primeira execução
- Para serviço Windows com `.exe`, use o NSSM apontando para `DailyNewsBot.exe` em vez de `python.exe`

## Solução de problemas

| Problema | Solução |
|----------|---------|
| `chat not found` | Verifique `TELEGRAM_CHAT_ID` e se o bot foi adicionado ao grupo |
| `Unauthorized` | Token do bot inválido em `TELEGRAM_BOT_TOKEN` |
| `AI_API_KEY` ausente | Preencha o `.env` |
| Timeout na NVIDIA | Reduza `AI_MAX_TOKENS` ou aumente a conexão |
| Mensagem cortada | O bot divide automaticamente; verifique os logs |
| Horário errado | Confirme `TIMEZONE=America/Sao_Paulo` e `tzdata` instalado |

## Licença

Uso livre para fins pessoais e comerciais.
