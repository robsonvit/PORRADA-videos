"""
gerar_voz.py
Sintetiza narração usando Kokoro TTS (pm_alex — voz masculina PT-BR, humana e natural).

Estratégia híbrida:
  1. edge-tts gera os timestamps palavra a palavra (preciso, gratuito)
  2. Kokoro gera o áudio final (qualidade humana, voz pm_alex)
  3. Os timestamps são escalonados proporcionalmente à duração do Kokoro
     → Legendas sincronizadas com precisão sem precisar de Whisper/GPU
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import edge_tts
import soundfile as sf
from kokoro_onnx import Kokoro

# ── Configurações ─────────────────────────────────────────────────────────────
KOKORO_VOICE  = "pm_alex"          # Voz escolhida pelo usuário
KOKORO_SPEED  = 0.88               # Velocidade (0.88 = ligeiramente pausado, mais impacto)
KOKORO_LANG   = "pt-br"

EDGE_VOICE    = "pt-BR-AntonioNeural"  # Usado APENAS para timestamps
EDGE_RATE     = "-8%"

# Pasta dos modelos Kokoro (configurável via variável de ambiente)
_MODELS_DIR   = Path(os.environ.get("KOKORO_MODELS_DIR", "."))
KOKORO_MODEL  = str(_MODELS_DIR / "kokoro-v1.0.onnx")
KOKORO_VOICES = str(_MODELS_DIR / "voices-v1.0.bin")


# ── Etapa 1: Timestamps via edge-tts ─────────────────────────────────────────
async def _extrair_timestamps_edge(texto: str) -> tuple[bytes, list]:
    """Extrai timestamps palavra a palavra via edge-tts."""
    communicate = edge_tts.Communicate(texto, EDGE_VOICE, rate=EDGE_RATE)
    timings = []
    audio_data = b""

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            timings.append({
                "word":     chunk["text"],
                "start":    chunk["offset"] / 10_000_000,
                "duration": chunk["duration"] / 10_000_000,
            })

    return audio_data, timings


# ── Etapa 2: Áudio Kokoro ─────────────────────────────────────────────────────
def _gerar_audio_kokoro(texto: str, output_wav: str) -> float:
    """Gera o áudio com Kokoro pm_alex e retorna a duração em segundos."""
    print(f"  Carregando modelo Kokoro de: {_MODELS_DIR}")
    kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)

    samples, sample_rate = kokoro.create(
        texto,
        voice=KOKORO_VOICE,
        speed=KOKORO_SPEED,
        lang=KOKORO_LANG,
    )

    sf.write(output_wav, samples, sample_rate)
    duracao = len(samples) / sample_rate
    print(f"  Audio Kokoro gerado: {output_wav} ({duracao:.1f}s)")
    return duracao


# ── Etapa 3: Escalonamento dos timestamps ─────────────────────────────────────
def _escalar_timings(timings: list, fator: float) -> list:
    """Escala todos os timestamps proporcionalmente."""
    return [
        {
            "word":     t["word"],
            "start":    t["start"] * fator,
            "duration": t["duration"] * fator,
        }
        for t in timings
    ]


# ── Função principal ──────────────────────────────────────────────────────────
async def _gerar_voz_async(texto: str, output_audio: str, output_timing: str) -> list:
    """
    Pipeline completo de geração de voz e timestamps.

    1. edge-tts → timestamps (ms precisão)
    2. Kokoro pm_alex → áudio humano (WAV)
    3. WAV → MP3 via ffmpeg
    4. Escala timestamps para duração real do Kokoro
    """
    work = Path(output_audio).parent
    wav_temp = str(work / "_kokoro_raw.wav")

    # ── Etapa 1: Timestamps ───────────────────────────────────────────────────
    print("  Extraindo timestamps via edge-tts...")
    _, timings_edge = await _extrair_timestamps_edge(texto)

    if not timings_edge:
        raise RuntimeError("Nenhum timestamp gerado pelo edge-tts")

    duracao_edge = timings_edge[-1]["start"] + timings_edge[-1]["duration"]
    print(f"  edge-tts: {len(timings_edge)} palavras, {duracao_edge:.1f}s")

    # ── Etapa 2: Áudio Kokoro ─────────────────────────────────────────────────
    print(f"  Gerando audio com Kokoro ({KOKORO_VOICE})...")
    duracao_kokoro = _gerar_audio_kokoro(texto, wav_temp)

    # ── Etapa 3: WAV → MP3 ───────────────────────────────────────────────────
    print("  Convertendo WAV para MP3...")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", wav_temp, "-b:a", "192k", output_audio],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg WAV->MP3 falhou:\n{result.stderr}")
    Path(wav_temp).unlink(missing_ok=True)

    # ── Etapa 4: Escala timestamps ────────────────────────────────────────────
    fator = duracao_kokoro / duracao_edge if duracao_edge > 0 else 1.0
    timings_finais = _escalar_timings(timings_edge, fator)
    print(f"  Fator de escala: {fator:.3f} (edge {duracao_edge:.1f}s → Kokoro {duracao_kokoro:.1f}s)")

    with open(output_timing, "w", encoding="utf-8") as f:
        json.dump(timings_finais, f, ensure_ascii=False, indent=2)

    print(f"  Audio final: {output_audio} | Timings: {len(timings_finais)} palavras")
    return timings_finais


def gerar_voz(texto: str, output_audio: str, output_timing: str) -> list:
    """Wrapper síncrono."""
    return asyncio.run(_gerar_voz_async(texto, output_audio, output_timing))


def calcular_duracao_audio(timing_file: str) -> float:
    """Calcula duração total do áudio a partir dos timings."""
    with open(timing_file, "r", encoding="utf-8") as f:
        timings = json.load(f)
    if not timings:
        return 0.0
    ultimo = timings[-1]
    return ultimo["start"] + ultimo["duration"]


# ── Teste standalone ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        print("Teste de geracao de voz com Kokoro pm_alex...")
        texto_teste = (
            "Tem pessoas que somem da sua vida exatamente quando voce mais precisa. "
            "Isso nao e coincidencia. Isso e quem elas sempre foram. "
            "A dor de ser abandonado ensina o que nenhum abraco consegue. "
            "Aprenda a valorizar sua propria companhia."
        )
        gerar_voz(texto_teste, "test_kokoro_audio.mp3", "test_kokoro_timing.json")
        print("OK! Arquivos: test_kokoro_audio.mp3 e test_kokoro_timing.json")
