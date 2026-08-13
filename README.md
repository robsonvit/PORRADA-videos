# 🎬 VÍDEOS PORRADA — Criador Automático de Vídeos

Pipeline automatizado de criação de vídeos curtos verticais de "verdades duras" usando IA, voz neural e vídeos do Pexels.

---

## 🚀 Como funciona

```
Grok API → Roteiro
  ↓
edge-tts → Voz Masculina (pt-BR-AntonioNeural)
  ↓
Pexels API → Clipes de vídeo (espelhados)
  ↓
FFmpeg → Vídeo 1080x1920 com legendas + HDR + Glow
  ↓
Telegram Bot → Envio automático
```

### Estrutura do vídeo gerado
- **0:00–0:04** → Clip dos "VÍDEOS DO SHELBY" (gancho visual)
- **0:04+** → Clipes do Pexels (espelhados horizontalmente)
- **Legenda** → Texto amarelo dourado, fonte Anton, centralizado
- **Áudio** → Narração masculina neural em PT-BR
- **Efeitos** → HDR (curves + saturation) + Glow suave

---

## ⚙️ Configuração

### 1. Criar repositório no GitHub

```bash
git init
git add .
git commit -m "🎬 Initial commit — PORRADA Video Pipeline"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/PORRADA-videos.git
git push -u origin main
```

### 2. Configurar GitHub Secrets

Vá em: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valor |
|--------|-------|
| `GROK_API_KEY` | Sua chave da API Grok (xAI) |
| `PEXELS_API_KEY` | Sua chave da API Pexels |
| `TELEGRAM_BOT_TOKEN` | Token do Bot Telegram |
| `TELEGRAM_CHAT_ID` | ID do chat/canal destino |

> **Como obter o TELEGRAM_CHAT_ID:**
> 1. Adicione o bot ao grupo/canal
> 2. Envie uma mensagem no grupo
> 3. Acesse: `https://api.telegram.org/botSEU_TOKEN/getUpdates`
> 4. Copie o `chat.id` da resposta

### 3. Executar manualmente

1. Vá em **Actions** no GitHub
2. Clique em **🎬 Gerar Vídeo PORRADA**
3. Clique em **Run workflow**
4. Escolha quantos vídeos gerar (1–10)
5. Clique em **Run workflow** verde

### 4. Agendamento automático

O workflow roda automaticamente **todo dia às 09:00** (horário de Brasília).

---

## 📁 Estrutura do projeto

```
CRIAÇÃO VIDEOS PORRADA/
├── .github/
│   └── workflows/
│       └── gerar_video.yml     # Workflow principal
├── VÍDEOS DO SHELBY/
│   ├── A (1).mp4               # Clips de gancho visual
│   ├── A (2).mp4
│   └── ...
├── scripts/
│   ├── pipeline.py             # Orquestrador principal
│   ├── gerar_roteiro.py        # Grok API → roteiro
│   ├── gerar_voz.py            # edge-tts → MP3 + timings
│   ├── buscar_videos_pexels.py # Pexels → download de clipes
│   ├── montar_video.py         # FFmpeg → montagem final
│   └── enviar_telegram.py      # Telegram Bot → envio
├── temas_usados.json           # Controle de 10 temas sem repetição
├── requirements.txt
└── README.md
```

---

## 🎨 Estilo das legendas

| Propriedade | Valor |
|-------------|-------|
| Fonte | Anton (similar ao Impact) |
| Tamanho | 82px |
| Cor | Amarelo dourado `#FFD700` |
| Outline | Preto, 5px |
| Posição | Centro vertical e horizontal |
| Exibição | 2–3 palavras por vez, em maiúsculas |

---

## 🔧 Temas de vídeo

O sistema gerencia automaticamente **20 temas** de "verdades duras", garantindo que os 10 próximos vídeos tenham temas diferentes. Após usar todos, a lista reinicia.

---

## 📋 Dependências

- `edge-tts` — Voz neural gratuita (Microsoft)
- `openai` — Cliente para API Grok (xAI)
- `requests` — HTTP para Pexels e Telegram
- `ffmpeg` — Montagem de vídeo (instalado no runner)
