"""
gerar_roteiro.py
Gera roteiros de "verdades duras" via API Grok (xAI).
Controla os temas usados para evitar repetições em 10 rodadas.
"""

import os
import json
import random
from pathlib import Path
from openai import OpenAI

# ── Configurações ─────────────────────────────────────────────────────────────
TEMAS_FILE = Path(__file__).parent.parent / "temas_usados.json"

TEMAS_BASE = [
    "solidão voluntária e por que ela cura",
    "amizades que só aparecem quando precisam de algo",
    "o preço real de mudar de vida",
    "pessoas que te subestimam até você vencer",
    "maturidade emocional que a vida ensina na dor",
    "relacionamentos tóxicos que você chama de amor",
    "o peso de crescer sem apoio emocional",
    "traição das pessoas em quem você confiava cegamente",
    "a ilusão de que alguém vai te salvar",
    "limites pessoais que você precisa aprender a impor",
    "inveja disfarçada de conselho e preocupação",
    "fracasso como o maior professor da sua vida",
    "a verdade cruel sobre quem some nas dificuldades",
    "autoconhecimento que dói mais que qualquer crítica",
    "silêncio que cura mais que mil palavras",
    "abandono que te ensinou a ser forte sozinho",
    "trabalho duro que nunca é visto pelos outros",
    "mudança que assusta porque exige perder conforto",
    "pessoas que drenam sua energia sem perceber",
    "a verdade sobre felicidade que ninguém te conta",
]

# ── Funções de controle de temas ──────────────────────────────────────────────
def carregar_temas_usados() -> list:
    """Carrega a lista de temas já usados do arquivo JSON."""
    if TEMAS_FILE.exists():
        with open(TEMAS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def salvar_tema_usado(tema: str) -> None:
    """Salva o tema usado no arquivo de controle."""
    usados = carregar_temas_usados()
    usados.append(tema)
    # Reset quando todos os temas forem usados
    if len(usados) >= len(TEMAS_BASE):
        print("🔄 Todos os temas foram usados. Reiniciando a lista.")
        usados = []
    with open(TEMAS_FILE, "w", encoding="utf-8") as f:
        json.dump(usados, f, ensure_ascii=False, indent=2)


def escolher_tema() -> str:
    """Escolhe um tema que ainda não foi usado recentemente."""
    usados = carregar_temas_usados()
    disponiveis = [t for t in TEMAS_BASE if t not in usados]
    if not disponiveis:
        # Todos usados — reinicia
        with open(TEMAS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        disponiveis = TEMAS_BASE
    tema = random.choice(disponiveis)
    print(f"🎯 Tema escolhido: {tema}")
    return tema


# ── Geração de roteiro via Grok ───────────────────────────────────────────────
def gerar_roteiro(tema: str) -> dict:
    """
    Chama a API Groq para gerar um roteiro completo de vídeo PORRADA.

    Returns:
        dict com chaves: titulo, roteiro_fala, palavras_chave_pexels, hashtags, tema
    """
    client = OpenAI(
        api_key=os.environ["GROK_API_KEY"],  # O secret no Github está como GROK_API_KEY
        base_url="https://api.groq.com/openai/v1",
    )

    prompt = f"""Você é um roteirista de vídeos virais chamados "PORRADA" — vídeos de verdades duras e impactantes para reflexão profunda.

Crie um roteiro completo para um vídeo curto (40–55 segundos de narração) sobre o tema: "{tema}"

RETORNE APENAS um JSON válido, sem markdown, com esta estrutura exata:
{{
    "titulo": "Título impactante em maiúsculas (máx 55 caracteres, sem emoji)",
    "roteiro_fala": "Texto completo da narração em português do Brasil. Frases curtas e impactantes separadas por ponto. Tom direto, maduro e honesto. COMECE com impacto total — sem 'olá', sem 'hoje vou falar', sem introduções genéricas. Verdades que as pessoas sentem mas têm medo de ouvir. Entre 130 e 170 palavras.",
    "palavras_chave_pexels": ["nature calm", "lonely animal wildlife", "sad rainy forest", "ocean waves"],
    "hashtags": "#reflexao #verdade #autoconhecimento #motivacao #crescimento"
}}

REGRAS CRÍTICAS:
- O roteiro deve começar diretamente com a verdade, sem rodeios
- Tom: sério, reflexivo, impactante — como uma voz que acorda a consciência
- Palavras-chave Pexels: em INGLÊS, temáticas de natureza triste, calma, solidão (ex: lonely wolf, misty forest, rainy lake, dark ocean, empty road)
- Exatamente 4 palavras-chave Pexels
- 5 hashtags em português"""

    print("🤖 Chamando API Groq para gerar roteiro...")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.85,
        max_tokens=1024,
    )

    result = json.loads(response.choices[0].message.content)
    result["tema"] = tema

    print(f"✅ Título: {result['titulo']}")
    print(f"📝 Roteiro ({len(result['roteiro_fala'].split())} palavras): {result['roteiro_fala'][:80]}...")
    print(f"🔍 Keywords Pexels: {result['palavras_chave_pexels']}")

    return result


# ── Execução standalone para teste ───────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        print("🧪 Modo de teste — verificando conexão com Grok...")
        tema = escolher_tema()
        roteiro = gerar_roteiro(tema)
        print("\n✅ Resultado:")
        print(json.dumps(roteiro, ensure_ascii=False, indent=2))
