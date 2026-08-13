"""
gerar_voz.py
Sintetiza voz masculina em PT-BR usando edge-tts (Microsoft Neural TTS).
Voz: pt-BR-AntonioNeural — Gratuita, sem API key, qualidade neural.
Gera áudio MP3 + arquivo JSON com timestamps por palavra (para sync de legendas).
"""

import asyncio
import json
import sys
from pathlib import Path

import edge_tts

# ── Configurações ─────────────────────────────────────────────────────────────
VOICE = "pt-BR-AntonioNeural"  # Voz masculina neural gratuita
VOICE_RATE = "-8%"             # Ligeiramente mais lento para mais impacto
VOICE_PITCH = "-2Hz"           # Tom ligeiramente mais grave


# ── Funções ───────────────────────────────────────────────────────────────────
async def _gerar_voz_async(texto: str, output_audio: str, output_timing: str) -> list:
    """
    Sintetiza o texto e captura timestamps por palavra.

    Returns:
        Lista de dicts {word, start, duration} com tempo em segundos
    """
    communicate = edge_tts.Communicate(texto, VOICE, rate=VOICE_RATE, pitch=VOICE_PITCH)

    word_timings = []
    audio_data = b""

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            word_timings.append({
                "word": chunk["text"],
                "start": chunk["offset"] / 10_000_000,      # 100ns → segundos
                "duration": chunk["duration"] / 10_000_000,  # 100ns → segundos
            })

    # Salva o áudio
    with open(output_audio, "wb") as f:
        f.write(audio_data)

    # Salva os timings
    with open(output_timing, "w", encoding="utf-8") as f:
        json.dump(word_timings, f, ensure_ascii=False, indent=2)

    duracao_total = word_timings[-1]["start"] + word_timings[-1]["duration"] if word_timings else 0
    print(f"✅ Áudio gerado: {output_audio}")
    print(f"✅ {len(word_timings)} palavras — duração: {duracao_total:.1f}s")

    return word_timings


def gerar_voz(texto: str, output_audio: str, output_timing: str) -> list:
    """Wrapper síncrono para o gerador de voz assíncrono."""
    return asyncio.run(_gerar_voz_async(texto, output_audio, output_timing))


def calcular_duracao_audio(timing_file: str) -> float:
    """Calcula a duração total do áudio a partir dos timings."""
    with open(timing_file, "r", encoding="utf-8") as f:
        timings = json.load(f)
    if not timings:
        return 0.0
    ultimo = timings[-1]
    return ultimo["start"] + ultimo["duration"]


# ── Execução standalone para teste ───────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        print("🧪 Modo de teste — gerando áudio de exemplo...")
        texto_teste = (
            "Nem todo mundo que ficou do seu lado te queria bem. "
            "Alguns estavam apenas esperando a hora certa de ir embora. "
            "Aprender a distinguir presença de lealdade é uma das lições mais duras da vida."
        )
        gerar_voz(
            texto=texto_teste,
            output_audio="test_audio.mp3",
            output_timing="test_timing.json",
        )
        print("✅ Arquivos gerados: test_audio.mp3 e test_timing.json")

    elif "--list-voices" in sys.argv:
        async def listar():
            voices = await edge_tts.list_voices()
            pt_voices = [v for v in voices if v["Locale"].startswith("pt-")]
            for v in pt_voices:
                print(f"  {v['ShortName']} — {v['Gender']}")
        asyncio.run(listar())
