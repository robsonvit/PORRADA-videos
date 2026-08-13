"""
gerar_voz.py
Sintetiza narração usando Kokoro TTS (pm_alex — voz masculina PT-BR).

Estratégia:
  1. Kokoro gera o áudio final (qualidade humana, voz pm_alex)
  2. Groq Whisper (via API) extrai os timestamps palavra a palavra
     do áudio gerado, garantindo precisão absoluta nas legendas.
"""

import os
import json
import subprocess
import sys
from pathlib import Path

import soundfile as sf
from kokoro_onnx import Kokoro
from openai import OpenAI

# ── Configurações ─────────────────────────────────────────────────────────────
KOKORO_VOICE  = "pm_alex"          # Voz escolhida pelo usuário
KOKORO_SPEED  = 0.88               # Velocidade (0.88 = ligeiramente pausado, mais impacto)
KOKORO_LANG   = "pt-br"

# Pasta dos modelos Kokoro (configurável via variável de ambiente)
_MODELS_DIR   = Path(os.environ.get("KOKORO_MODELS_DIR", "."))
KOKORO_MODEL  = str(_MODELS_DIR / "kokoro-v1.0.onnx")
KOKORO_VOICES = str(_MODELS_DIR / "voices-v1.0.bin")


# ── Etapa 1: Áudio Kokoro ─────────────────────────────────────────────────────
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


# ── Etapa 2: Timestamps via Groq Whisper ──────────────────────────────────────
def _extrair_timestamps_groq(audio_path: str) -> list:
    """Extrai timestamps palavra a palavra via Groq Whisper API."""
    print("  Extraindo timestamps via Groq Whisper...")
    client = OpenAI(
        api_key=os.environ["GROK_API_KEY"],
        base_url="https://api.groq.com/openai/v1",
    )

    with open(audio_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-large-v3",
            response_format="verbose_json",
            timestamp_granularities=["word"]
        )

    timings = []
    
    # Extrai os dados independentemente da versão do SDK da OpenAI (Pydantic vs dict)
    try:
        t_data = transcription.model_dump()
    except AttributeError:
        t_data = transcription if isinstance(transcription, dict) else vars(transcription)

    words = t_data.get("words", [])
    if not words:
        raise RuntimeError("Nenhuma palavra retornada pelo Groq Whisper")

    for w in words:
        timings.append({
            "word": w["word"],
            "start": w["start"],
            "duration": w["end"] - w["start"],
        })

    return timings


# ── Função principal ──────────────────────────────────────────────────────────
def gerar_voz(texto: str, output_audio: str, output_timing: str) -> list:
    """
    Pipeline completo de geração de voz e timestamps.

    1. Kokoro pm_alex → áudio humano (WAV)
    2. WAV → MP3 via ffmpeg
    3. Groq Whisper → Extrai timestamps precisos do MP3
    """
    work = Path(output_audio).parent
    wav_temp = str(work / "_kokoro_raw.wav")

    # ── Etapa 1: Áudio Kokoro ─────────────────────────────────────────────────
    print(f"  Gerando audio com Kokoro ({KOKORO_VOICE})...")
    duracao_kokoro = _gerar_audio_kokoro(texto, wav_temp)

    # ── Etapa 2: WAV → MP3 ───────────────────────────────────────────────────
    print("  Convertendo WAV para MP3...")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", wav_temp, "-b:a", "192k", output_audio],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg WAV->MP3 falhou:\n{result.stderr}")
    Path(wav_temp).unlink(missing_ok=True)

    # ── Etapa 3: Timestamps via Groq ──────────────────────────────────────────
    timings = _extrair_timestamps_groq(output_audio)

    with open(output_timing, "w", encoding="utf-8") as f:
        json.dump(timings, f, ensure_ascii=False, indent=2)

    print(f"  Audio final: {output_audio} | Timings: {len(timings)} palavras")
    return timings


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
        print("Teste de geracao de voz com Kokoro + Groq Whisper...")
        texto_teste = (
            "Tem pessoas que somem da sua vida exatamente quando voce mais precisa. "
            "Isso nao e coincidencia. Isso e quem elas sempre foram. "
            "A dor de ser abandonado ensina o que nenhum abraco consegue. "
            "Aprenda a valorizar sua propria companhia."
        )
        gerar_voz(texto_teste, "test_kokoro_audio.mp3", "test_kokoro_timing.json")
        print("OK! Arquivos: test_kokoro_audio.mp3 e test_kokoro_timing.json")
