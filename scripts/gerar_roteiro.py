"""
gerar_roteiro.py
Gera roteiros virais de "verdades duras" via OpenRouter API.
Usa modelos gratuitos (:free) com fallback automático entre eles.
Controla os temas usados para evitar repetições em 20 rodadas.
"""

import os
import json
import random
import sys
import re
import time
from pathlib import Path
from openai import OpenAI

# ── Configurações OpenRouter ───────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ── Configurações Grok (xAI) Fallback ──────────────────────────────────────────
GROK_API_KEY = os.environ.get("GROK_API_KEY", "")
GROK_BASE_URL = "https://api.x.ai/v1"

# Modelos gratuitos em ordem de preferência — sufixo :free = sem custo
# Lista atualizada em agosto/2026 — verificada via API: https://openrouter.ai/api/v1/models
# ATENÇÃO: A lista anterior tinha modelos obsoletos/inexistentes (llama-3.1-8b:free,
# phi-3-mini:free, gemma-4-31b:free, nemotron-3-nano:free, glm-5.2:free).
# O "openrouter/auto:free" também não existe mais — o correto é "openrouter/free".
MODELOS_GRATUITOS = [
    "openrouter/free",                                    # Router auto — escolhe o melhor free disponível
    "nvidia/nemotron-3.5-lightning:free",                 # NVIDIA 30B MoE — contexto 1M tokens
    "dots-studio/dots-3-note-preview:free",               # Dots Studio 280B MoE — alta qualidade
    "inclusionai/ling-3.0-flash-fin:free",                # InclusionAI 124B MoE — rápido
    "liquid/lfm-2.5-2.6b:free",                          # LiquidAI — compacto mas funcional
    "meta-llama/llama-4-scout:free",                     # Meta Llama 4 Scout
    "google/gemma-3-27b-it:free",                        # Google Gemma 3 27B
    "qwen/qwen3-8b:free",                                # Qwen 8B
    "mistralai/mistral-small-3.2-24b-instruct:free",     # Mistral 24B
]

TEMAS_FILE = Path(__file__).parent.parent / "temas_usados.json"

TEMAS_BASE = [
    "pessoas que somem quando você mais precisa delas",
    "amizades falsas que só aparecem quando precisam de algo",
    "o preço real de mudar de vida e perder pessoas no caminho",
    "pessoas que te subestimam até você vencer",
    "maturidade emocional que a vida ensina na dor",
    "relacionamentos onde só você se esforça",
    "o peso de crescer sem apoio emocional de ninguém",
    "traição das pessoas em quem você confiava cegamente",
    "a ilusão de que alguém vai te salvar",
    "limites pessoais que você precisa aprender a impor agora",
    "inveja disfarçada de conselho e preocupação com você",
    "a verdade cruel sobre quem desaparece nas suas dificuldades",
    "solidão voluntária como forma de cura e autoconhecimento",
    "silêncio como resposta para quem não merece explicação",
    "abandono que te ensinou a ser forte sozinho",
    "trabalho duro e esforço que nunca é reconhecido pelos outros",
    "mudança de vida que assusta porque exige perder o conforto",
    "pessoas que drenam sua energia sem você perceber",
    "a verdade sobre felicidade que os outros não querem que você saiba",
    "ingratidão de quem você ajudou quando mais precisava",
]

# ── Prompt Mestre ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Você é um roteirista especialista em vídeos virais para TikTok, Instagram Reels e YouTube Shorts, especializado em conteúdo de reflexão profunda, comportamento humano, relacionamentos, autoestima, traição, decepções, inveja, superação, disciplina, silêncio, maturidade e desenvolvimento pessoal.

Sua missão é receber um TEMA, DOR ou SITUAÇÃO e transformar isso em um roteiro altamente emocional, compartilhável e viciante, seguindo a engenharia psicológica dos vídeos virais no estilo "Sigma": narração marcante, frases de impacto, reflexão profunda, indiretas que geram identificação e cenas cinematográficas ou de natureza como plano de fundo.

OBJETIVO PRINCIPAL:
Crie roteiros que façam a pessoa pensar:
"Isso aconteceu comigo."
"Parece que ele está falando exatamente da minha vida."
"Preciso mandar esse vídeo para alguém."
"Eu precisava ouvir isso."

ESTRUTURA OBRIGATÓRIA:
1. GANCHO (0-3s): Frase extremamente forte, direta e impossível de ignorar. Aborda uma dor universal ou revela uma verdade desconfortável. NUNCA comece com "Hoje eu quero falar sobre…", "Você já parou para pensar…", "Olá pessoal…".

2. IDENTIFICAÇÃO COM A DOR: Situação extremamente específica e familiar. Explore sentimentos como abandono, rejeição, ingratidão, amizade falsa, falta de reciprocidade, traição, humilhação, solidão, inveja, desprezo, esforço unilateral.

3. DESENVOLVIMENTO - A VERDADE INCÔMODA: Revelação mais profunda. Evolução: DOR → PERCEPÇÃO → VERDADE → MATURIDADE.

4. VIRADA EMOCIONAL: Mudança de perspectiva. O que parecia uma perda pode ser um livramento.

5. FRASES "TAPA NA CARA": 3-6 frases curtas e extremamente compartilháveis, funcionam isoladamente como indiretas.

6. CONCLUSÃO: Sensação de força, paz, maturidade ou libertação. O personagem não termina como vítima.

7. CTA VIRAL: Natural e emocional, parte da mensagem, não propaganda.

ESTILO: Frases curtas, pausas naturais, perguntas retóricas, intensidade emocional. Escreva como alguém contando uma verdade que aprendeu depois de sofrer. Use "você", "a gente", "pra", "tá". NÃO escreva como IA.

LINGUAGEM: Este roteiro é narrado por uma voz no estilo Thomas Shelby — bruto, direto e sem filtro. Use um palavrão de forma NATURAL e PODEROSA APENAS no gancho inicial para chamar a atenção. No restante do texto, mantenha o tom sério e bruto, mas SEM palavrões.
- Exemplos de palavrões para o gancho: Porra, Caralho, Cacete, Merda, Bosta, Babaca, Filha da puta, Desgraça.
- O palavrão deve FORTALECER a primeira frase, como um desabafo sincero.

REGRAS:
1. Não copie nenhum roteiro existente
2. Não use clichês excessivamente conhecidos
3. Não faça o roteiro parecer escrito por IA
4. Não encha de metáforas
5. Não faça introdução desnecessária
6. Priorize identificação emocional
7. O gancho OBRIGATORIAMENTE deve conter UM palavrão forte — é a primeira coisa que o ouvinte escuta.
8. NÃO coloque palavrões no resto do roteiro, apenas na primeira frase.
9. A última frase antes do CTA deve ser memorável

COMPRIMENTO: 100 a 140 palavras de narração."""

# ── Controle de temas ─────────────────────────────────────────────────────────
def carregar_temas_usados() -> list:
    if TEMAS_FILE.exists():
        with open(TEMAS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def salvar_tema_usado(tema: str) -> None:
    usados = carregar_temas_usados()
    usados.append(tema)
    if len(usados) >= len(TEMAS_BASE):
        print("Todos os temas foram usados. Reiniciando a lista.")
        usados = []
    with open(TEMAS_FILE, "w", encoding="utf-8") as f:
        json.dump(usados, f, ensure_ascii=False, indent=2)


def escolher_tema() -> str:
    usados = carregar_temas_usados()
    disponiveis = [t for t in TEMAS_BASE if t not in usados]
    if not disponiveis:
        with open(TEMAS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        disponiveis = TEMAS_BASE
    tema = random.choice(disponiveis)
    print(f"Tema escolhido: {tema}")
    return tema


# ── Limpeza de reasoning tags ─────────────────────────────────────────────────
def _remover_reasoning(content: str) -> str:
    """
    Remove blocos de raciocínio interno que modelos de thinking retornam.
    Modelos como GLM, Nemotron, LFM etc retornam <think>...</think> ANTES
    do JSON real — isso causava JSONDecodeError. Esta função limpa esses blocos.

    Exemplo do problema no log:
      <think>
        Here's a thinking process...  (centenas de linhas)
      </think>
      { "titulo": "...", ... }   <- o JSON real fica depois
    """
    # Remove <think>...</think> (captura blocos longo com DOTALL)
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)
    # Remove <reasoning>...</reasoning>
    content = re.sub(r'<reasoning>.*?</reasoning>', '', content, flags=re.DOTALL | re.IGNORECASE)
    # Remove <think> solto sem fechamento (modelo parou no meio do raciocínio)
    content = re.sub(r'<think>.*', '', content, flags=re.DOTALL | re.IGNORECASE)
    return content.strip()


# ── Extrator de JSON robusto ──────────────────────────────────────────────────
def _extrair_json(content: str) -> dict:
    """
    Extrai o JSON da resposta do modelo com múltiplas estratégias.
    Lida com modelos que retornam raciocínio, markdown ou texto extra.
    """
    # Pré-processamento: remove tags de reasoning (<think>, <reasoning>, etc.)
    content = _remover_reasoning(content)

    # Estratégia 1: parse direto
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        pass

    # Estratégia 2: remove blocos markdown ```json ... ```
    limpo = re.sub(r'```(?:json)?\s*', '', content)
    limpo = re.sub(r'```\s*', '', limpo)
    try:
        return json.loads(limpo.strip())
    except json.JSONDecodeError:
        pass

    # Estratégia 3: maior bloco {...} válido com chaves obrigatórias
    candidatos = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
    for cand in sorted(candidatos, key=len, reverse=True):
        try:
            obj = json.loads(cand)
            if "titulo" in obj and "roteiro_fala" in obj:
                return obj
        except json.JSONDecodeError:
            continue

    # Estratégia 4: greedy do primeiro { ao último }
    primeiro = content.find('{')
    ultimo = content.rfind('}')
    if primeiro != -1 and ultimo != -1 and ultimo > primeiro:
        try:
            return json.loads(content[primeiro:ultimo + 1])
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON inválido após todas as estratégias. Erro: {e}\nConteúdo: {content[:400]}")

    raise ValueError(f"Nenhum JSON encontrado. Conteúdo: {content[:400]}")


# ── Geração de roteiro via OpenRouter ─────────────────────────────────────────
def gerar_roteiro(tema: str) -> dict:
    """
    Gera o roteiro viral via OpenRouter usando modelos gratuitos.
    Caso todos os modelos falhem por rate limit, ativa o fallback para xAI Grok.
    """
    if not OPENROUTER_API_KEY and not GROK_API_KEY:
        raise RuntimeError("Nenhuma chave (OPENROUTER_API_KEY ou GROK_API_KEY) definida!")

    user_prompt = f"""Tema: {tema}

Com base no tema acima, crie o roteiro completo seguindo todas as regras do sistema.

CRÍTICO E OBRIGATÓRIO: VOCÊ DEVE RETORNAR APENAS E EXCLUSIVAMENTE O OBJETO JSON.
NÃO ESCREVA NENHUMA PALAVRA ANTES OU DEPOIS. NÃO ESCREVA RACIOCÍNIOS NEM EXPLICAÇÕES.
SUA RESPOSTA INTEIRA DEVE COMEÇAR COM A CHAVE E TERMINAR COM A CHAVE.

Retorne APENAS um JSON válido com esta estrutura exata (sem markdown, sem texto extra):
{{
    "titulo": "TÍTULO EM MAIÚSCULAS — impactante e curto (máx 55 chars)",
    "roteiro_fala": "Texto completo da narração. Frases curtas separadas por ponto. 100-140 palavras. Comece com o gancho forte.",
    "palavras_chave_pexels": ["natureza imponente 1", "situacao emocional 1", "natureza imponente 2", "situacao emocional 2"],
    "hashtags_tema": ["#palavrachave1", "#palavrachave2", "#palavrachave3"]
}}

Para palavras_chave_pexels, use termos em INGLÊS que combinem com o tema visualmente.
Você deve alternar entre:
1. Vídeos de natureza imponente (ex: "dark forest", "waterfall", "imposing lion", "stormy ocean", "mountain peak")
2. Pessoas em situações relacionadas ao roteiro (ex: "person crying alone", "fake friendship", "person walking away", "lonely man", "sad woman")
- Exatamente 4 palavras-chave (2 de natureza, 2 de situações de pessoas)

Para hashtags_tema, gere EXATAMENTE 3 hashtags em português (sem espaços, sem acentos, letras minúsculas):
- Exemplos: #traicao #amizadefalsa #abandono #solidao #superacao #maturidade"""

    print("Chamando OpenRouter para gerar roteiro...")

    last_error = None
    result = None

    if OPENROUTER_API_KEY:
        client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )

        for modelo in MODELOS_GRATUITOS:
            try:
                print(f"  Tentando: {modelo}...")
                response = client.chat.completions.create(
                    model=modelo,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=1500,
                    extra_headers={
                        "HTTP-Referer": "https://github.com/robsonvit/PORRADA-videos",
                        "X-Title": "PORRADA Videos Bot",
                    },
                )

                content = (response.choices[0].message.content or "").strip()
                # Log primeiros 300 chars para debug (pode incluir <think> antes)
                print(f"  Resposta bruta (300 chars): {content[:300]}...")

                if not content:
                    raise ValueError(f"{modelo} retornou conteúdo vazio")

                result = _extrair_json(content)
                print(f"  ✅ Roteiro gerado com sucesso via {modelo}")
                break

            except Exception as e:
                print(f"  ⚠️ Falhou com {modelo}: {e}")
                last_error = e
                # Pausa estratégica para evitar Rate Limits (429) em cascata
                time.sleep(3)
                continue
    else:
        print("  ⚠️ OPENROUTER_API_KEY ausente. Pulando OpenRouter...")

    # ── Fallback xAI Grok ─────────────────────────────────────────────────────
    if result is None and GROK_API_KEY:
        print(f"\n  🔄 Todos os modelos OpenRouter falharam (ou sem chave). Ativando Fallback Grok...")
        try:
            grok_client = OpenAI(
                api_key=GROK_API_KEY,
                base_url=GROK_BASE_URL,
            )
            response = grok_client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )

            content = (response.choices[0].message.content or "").strip()
            print(f"  Resposta Grok: {content[:200]}...")
            if not content:
                raise ValueError("Grok retornou conteúdo vazio")

            result = _extrair_json(content)
            print(f"  ✅ Roteiro gerado com sucesso via Grok (grok-beta)")
        except Exception as e:
            print(f"  ⚠️ Fallback Grok falhou: {e}")
            last_error = e

    if result is None:
        raise ValueError(f"Todas as tentativas falharam (OpenRouter e Grok). Último erro: {last_error}")

    result["tema"] = tema

    # Monta campo 'hashtags' unificado
    hashtags_tema = result.get("hashtags_tema", [])
    if isinstance(hashtags_tema, list) and hashtags_tema:
        hashtags_str = " ".join(hashtags_tema[:3]) + " #videoparastatus #reflexao"
    else:
        hashtags_str = "#videoparastatus #reflexao"
    result["hashtags"] = hashtags_str

    print(f"Titulo: {result['titulo']}")
    palavras = len(result['roteiro_fala'].split())
    print(f"Roteiro ({palavras} palavras): {result['roteiro_fala'][:80]}...")
    print(f"Keywords Pexels: {result['palavras_chave_pexels']}")
    print(f"Hashtags: {result['hashtags']}")

    return result


# ── Teste standalone ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        print("Modo de teste — verificando conexao com OpenRouter...")
        tema = escolher_tema()
        roteiro = gerar_roteiro(tema)
        print("\nResultado:")
        print(json.dumps(roteiro, ensure_ascii=False, indent=2))
