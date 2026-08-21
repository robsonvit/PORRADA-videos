"""
gerar_voz.py
Sintetiza narração com estratégia dupla:

  PRIMÁRIA  → Fish Audio API (modelo s2.1-pro-free, voz clonada 86f23b65...)
  FALLBACK  → Kokoro TTS local (pm_santa, PT-BR) — usado se o Fish falhar

Após gerar o áudio (de qualquer uma das fontes), o Groq Whisper extrai
os timestamps palavra a palavra para garantir precisão nas legendas.
"""

import os
import json
import time
import subprocess
import sys
from pathlib import Path

import soundfile as sf
import requests
from openai import OpenAI

# ── Configurações Fish Audio ──────────────────────────────────────────────────
FISH_API_KEY    = os.environ.get("FISH_API_KEY", "")
FISH_VOICE_ID   = "86f23b6596304f22955de78fe89638fc"   # Voz já clonada no Fish
FISH_MODEL      = "s2.1-pro-free"                       # Modelo gratuito
FISH_API_URL    = "https://api.fish.audio/v1/tts"

# ── Configurações Kokoro (fallback) ───────────────────────────────────────────
KOKORO_VOICE  = "pm_santa"
KOKORO_SPEED  = 0.80
KOKORO_LANG   = "pt-br"
_MODELS_DIR   = Path(os.environ.get("KOKORO_MODELS_DIR", "."))
KOKORO_MODEL  = str(_MODELS_DIR / "kokoro-v1.0.onnx")
KOKORO_VOICES = str(_MODELS_DIR / "voices-v1.0.bin")


# ── Etapa 1-A: Áudio via Fish Audio API ──────────────────────────────────────
def _gerar_audio_fish(texto: str, output_mp3: str) -> float:
    """
    Gera o áudio via Fish Audio API (s2.1-pro-free, voz clonada).
    Retorna a duração em segundos ou levanta exceção em caso de erro.
    """
    if not FISH_API_KEY:
        raise RuntimeError("FISH_API_KEY não definida — pulando Fish Audio.")

    print(f"  [Fish Audio] Enviando texto para a API (modelo: {FISH_MODEL})...")

    headers = {
        "Authorization": f"Bearer {FISH_API_KEY}",
        "Content-Type": "application/json",
        "model": FISH_MODEL,
    }
    payload = {
        "text": texto,
        "reference_id": FISH_VOICE_ID,
        "format": "mp3",
        "mp3_bitrate": 192,
        "normalize": True,
        "latency": "normal",
    }

    resp = requests.post(FISH_API_URL, json=payload, headers=headers, timeout=120)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Fish Audio API retornou status {resp.status_code}: {resp.text[:300]}"
        )

    # Salva o MP3 retornado
    Path(output_mp3).write_bytes(resp.content)

    # Calcula duração via ffprobe
    dur_result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_mp3,
        ],
        capture_output=True, text=True,
    )
    duracao = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 0.0
    print(f"  [Fish Audio] OK! Áudio gerado: {output_mp3} ({duracao:.1f}s)")
    return duracao


# ── Etapa 1-B: Áudio via Kokoro local (fallback) ─────────────────────────────
def _gerar_audio_kokoro(texto: str, output_wav: str) -> float:
    """Gera o áudio com Kokoro localmente (modo fallback)."""
    # Importação lazy — só carrega se o Kokoro for realmente usado
    from kokoro_onnx import Kokoro  # noqa: PLC0415

    print(f"  [Kokoro FALLBACK] Carregando modelo de: {_MODELS_DIR}")
    kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)

    samples, sample_rate = kokoro.create(
        texto,
        voice=KOKORO_VOICE,
        speed=KOKORO_SPEED,
        lang=KOKORO_LANG,
    )

    sf.write(output_wav, samples, sample_rate)
    duracao = len(samples) / sample_rate
    print(f"  [Kokoro FALLBACK] Áudio gerado: {output_wav} ({duracao:.1f}s)")
    return duracao


# ── Etapa 2: Timestamps via OpenRouter (Whisper) ───────────────────────────────
def _extrair_timestamps_openrouter(audio_path: str) -> list:
    """Extrai timestamps palavra a palavra via OpenRouter Whisper API."""
    print("  Extraindo timestamps via OpenRouter Whisper...")
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )

    with open(audio_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=audio_file,
            model="openai/whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )

    timings = []
    try:
        t_data = transcription.model_dump()
    except AttributeError:
        t_data = transcription if isinstance(transcription, dict) else vars(transcription)

    words = t_data.get("words", [])
    if not words:
        raise RuntimeError("Nenhuma palavra retornada pelo OpenRouter Whisper")

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
    Pipeline de geração de voz com fallback automático.

    1º Tenta Fish Audio API (s2.1-pro-free, voz clonada)
       → Se falhar, usa Kokoro local (pm_santa, PT-BR)
    2. Qualquer que seja a fonte, converte para MP3 se necessário
    3. OpenRouter Whisper extrai timestamps precisos
    """
    work = Path(output_audio).parent
    fonte_usada = "?"

    # ── Tentativa 1: Fish Audio ───────────────────────────────────────────────
    try:
        _gerar_audio_fish(texto, output_audio)
        fonte_usada = "Fish Audio (s2.1-pro-free)"
    except Exception as err_fish:
        print(f"\n  ⚠️  Fish Audio falhou: {err_fish}")
        print("  🔄 Ativando fallback: Kokoro TTS local...\n")

        # ── Fallback: Kokoro ──────────────────────────────────────────────────
        wav_temp = str(work / "_kokoro_raw.wav")
        _gerar_audio_kokoro(texto, wav_temp)

        # Converte WAV → MP3
        print("  Convertendo WAV para MP3 (fallback Kokoro)...")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", wav_temp, "-b:a", "192k", output_audio],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg WAV→MP3 falhou:\n{result.stderr}")
        Path(wav_temp).unlink(missing_ok=True)
        fonte_usada = f"Kokoro FALLBACK ({KOKORO_VOICE})"

    # ── Timestamps via OpenRouter ─────────────────────────────────────────────
    timings = _extrair_timestamps_openrouter(output_audio)

    with open(output_timing, "w", encoding="utf-8") as f:
        json.dump(timings, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ Voz gerada via: {fonte_usada}")
    print(f"  🎵 Áudio: {output_audio} | ⏱️  Timings: {len(timings)} palavras")
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
        print("Teste de geração de voz: Fish Audio → (fallback) Kokoro + OpenRouter Whisper")
        texto_teste = (
            "Tem pessoas que somem da sua vida exatamente quando você mais precisa. "
            "Isso não é coincidência. Isso é quem elas sempre foram. "
            "A dor de ser abandonado ensina o que nenhum abraço consegue. "
            "Aprenda a valorizar sua própria companhia."
        )
        gerar_voz(texto_teste, "test_audio.mp3", "test_timing.json")
        print("OK! Arquivos: test_audio.mp3 e test_timing.json")
