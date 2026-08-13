"""
montar_video.py
Montagem final do vídeo PORRADA usando FFmpeg.

Estrutura do vídeo (1080x1920 vertical):
  ├─ 0:00–0:04  → Clip Shelby (gancho visual / capa)
  ├─ 0:04+      → Clips Pexels (espelhados, 3s cada)
  ├─ Audio      → Narração começa no SEGUNDO 0 (junto com Shelby)
  ├─ Legendas   → Aparecem desde o SEGUNDO 0, amarelo dourado, centro
  ├─ HDR        → curves strong_contrast + eq saturation/contrast
  └─ Glow       → gblur leve + blend screen (brilho fraco)
"""

import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path


# ── Configurações ─────────────────────────────────────────────────────────────
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
SHELBY_CLIP_DURATION = 4.0   # Segundos do clip Shelby no início
MAX_CLIP_DURATION    = 3.0   # MÁXIMO 3s por clip Pexels (evita cópias)
FONT_FILE = "/usr/share/fonts/truetype/anton/Anton-Regular.ttf"
FONT_SIZE = 84


# ── Utilidades FFmpeg ─────────────────────────────────────────────────────────
def get_media_duration(filepath: str) -> float:
    """Retorna duração de um arquivo de mídia via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if "duration" in stream:
            return float(stream["duration"])
    return 0.0


def run_ffmpeg(args: list, description: str = "") -> None:
    """Executa um comando FFmpeg."""
    if description:
        print(f"  [FFmpeg] {description}...")
    cmd = ["ffmpeg", "-y"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERRO FFmpeg:\n{result.stderr[-3000:]}")
        raise RuntimeError(f"FFmpeg falhou: {description}")


# ── Geração de legendas via drawtext ─────────────────────────────────────────
def _escape_drawtext(texto: str) -> str:
    """Escapa caracteres especiais para o filtro drawtext do FFmpeg."""
    texto = texto.replace("\\", "\\\\")
    texto = texto.replace("'",  "\\'")
    texto = texto.replace(":",  "\\:")
    texto = texto.replace("%",  "\\%")
    return texto


def gerar_filtro_legendas(word_timings: list, font_file: str, offset: float = 0.0) -> str:
    """
    Gera cadeia de filtros drawtext para legendas palavra a palavra.

    Cada bloco mostra 2-3 palavras em maiúsculas, centralizadas na tela,
    amarelo dourado com outline preto espesso.

    Args:
        word_timings: Lista [{word, start, duration}] do edge-tts
        font_file: Caminho absoluto da fonte TrueType
        offset: Deslocamento em segundos (0 = começa junto com o áudio)

    Returns:
        String de filtros FFmpeg prontos para uso no filter_complex
    """
    if not word_timings:
        return "null"

    # ── Agrupa em blocos de 2-3 palavras ────────────────────────────────────
    grupos = []
    grupo_atual = []

    for i, timing in enumerate(word_timings):
        grupo_atual.append(timing)
        prox_inicio = word_timings[i + 1]["start"] if i < len(word_timings) - 1 else float("inf")
        fim_atual   = timing["start"] + timing["duration"]
        pausa       = prox_inicio - fim_atual

        if len(grupo_atual) >= 3 or pausa > 0.75:
            grupos.append(grupo_atual)
            grupo_atual = []

    if grupo_atual:
        grupos.append(grupo_atual)

    # ── Gera um filtro drawtext por bloco ────────────────────────────────────
    filtros = []
    for grupo in grupos:
        inicio = grupo[0]["start"] + offset
        fim    = grupo[-1]["start"] + grupo[-1]["duration"] + offset + 0.10
        # Garante mínimo de 0.35s de exibição
        if fim - inicio < 0.35:
            fim = inicio + 0.35

        texto          = " ".join(w["word"].upper() for w in grupo)
        texto_escapado = _escape_drawtext(texto)

        f = (
            f"drawtext="
            f"fontfile={font_file}:"
            f"text='{texto_escapado}':"
            f"fontsize={FONT_SIZE}:"
            f"fontcolor=#FFD700:"       # Amarelo dourado (igual à imagem)
            f"borderw=5:"               # Outline preto espesso
            f"bordercolor=black:"
            f"x=(w-text_w)/2:"         # Centralizado horizontalmente
            f"y=(h-text_h)/2:"         # Centralizado verticalmente (centro exato)
            f"enable='between(t,{inicio:.3f},{fim:.3f})'"
        )
        filtros.append(f)

    if not filtros:
        return "null"

    return ",".join(filtros)


# ── Processamento individual de clipes ────────────────────────────────────────
def processar_clip_vertical(
    input_path: str,
    output_path: str,
    duracao: float,
    aplicar_hflip: bool = False,
) -> None:
    """
    Converte clipe para formato vertical 1080x1920.
    Scale + crop centralizado + opcional hflip.
    """
    hflip_str = "hflip," if aplicar_hflip else ""
    vf = (
        f"{hflip_str}"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"setsar=1"
    )
    run_ffmpeg([
        "-i", input_path,
        "-t", str(duracao),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "22", "-preset", "fast",
        "-an",
        output_path,
    ], description=f"Convertendo {Path(input_path).name} ({duracao:.1f}s)")


# ── Função principal de montagem ──────────────────────────────────────────────
def montar_video(
    shelby_clips: list,
    pexels_clips: list,
    audio_file: str,
    word_timings: list,
    output_file: str,
    work_dir: str,
) -> str:
    """
    Monta o vídeo final completo.

    Estrutura de tempo:
      - Vídeo: [Shelby 4s] + [Pexels clips 3s cada]
      - Áudio: Narração começa no SEGUNDO 0 (junto com Shelby visual)
      - Legendas: Começam no SEGUNDO 0 (sem offset — sincronizadas com áudio)

    Returns:
        Path do vídeo final gerado
    """
    work = Path(work_dir)

    # ── 1. Duração do áudio ───────────────────────────────────────────────────
    duracao_audio = get_media_duration(audio_file)
    print(f"\nDuracao do audio: {duracao_audio:.1f}s")

    # Duração total: Shelby + clipes Pexels que cobrem a narração
    duracao_pexels_necessaria = max(1.0, duracao_audio - SHELBY_CLIP_DURATION)
    duracao_total = SHELBY_CLIP_DURATION + duracao_pexels_necessaria
    print(f"Duracao total do video: {duracao_total:.1f}s")

    # ── 2. Clip Shelby ────────────────────────────────────────────────────────
    print("\nProcessando clip Shelby...")
    shelby_escolhido = random.choice(shelby_clips)
    shelby_dur_orig  = get_media_duration(shelby_escolhido)
    shelby_dur       = min(SHELBY_CLIP_DURATION, shelby_dur_orig)
    shelby_out       = str(work / "shelby_proc.mp4")
    processar_clip_vertical(shelby_escolhido, shelby_out, shelby_dur, aplicar_hflip=False)

    # ── 3. Clips Pexels (espelhados, máx 3s cada) ────────────────────────────
    print("\nProcessando clips Pexels...")
    pexels_processados = []
    acumulado = 0.0
    idx = 0

    while acumulado < duracao_pexels_necessaria:
        clip_orig = pexels_clips[idx % len(pexels_clips)]
        dur_orig  = get_media_duration(clip_orig)
        # MÁXIMO 3 segundos por clipe Pexels
        dur_clip  = min(dur_orig, MAX_CLIP_DURATION, duracao_pexels_necessaria - acumulado)
        if dur_clip < 0.5:
            break

        out_clip = str(work / f"pexels_{idx:02d}.mp4")
        processar_clip_vertical(clip_orig, out_clip, dur_clip, aplicar_hflip=True)
        pexels_processados.append(out_clip)
        acumulado += dur_clip
        idx += 1

    print(f"  {len(pexels_processados)} clips Pexels ({acumulado:.1f}s)")

    # ── 4. Concatena Shelby + Pexels ─────────────────────────────────────────
    print("\nConcatenando clips...")
    concat_txt = str(work / "concat.txt")
    todos = [shelby_out] + pexels_processados

    with open(concat_txt, "w") as f:
        for c in todos:
            f.write(f"file '{c}'\n")

    video_concat = str(work / "video_concat.mp4")
    run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        video_concat,
    ], description="Concatenando todos os clips")

    # ── 5. Monta vídeo final ──────────────────────────────────────────────────
    # Áudio começa no segundo 0 (SEM silêncio de introdução)
    # Legendas aparecem desde o segundo 0 (offset=0)
    print("\nGerando filtro de legendas (drawtext)...")
    legenda_filter = gerar_filtro_legendas(
        word_timings=word_timings,
        font_file=FONT_FILE,
        offset=0.0,   # Legendas sincronizadas com o áudio desde o segundo 0
    )

    # Filter complex completo:
    # 1. Legendas (drawtext palavra a palavra)
    # 2. HDR: curves + eq
    # 3. Glow: gblur + blend screen fraco
    filter_complex = (
        f"[0:v]{legenda_filter},"
        f"curves=preset=strong_contrast,"
        f"eq=saturation=1.40:contrast=1.12:brightness=0.02,"
        f"split[vmain][vcopy];"
        f"[vcopy]gblur=sigma=7[vblur];"
        f"[vmain][vblur]blend=all_mode=screen:all_opacity=0.12[vout]"
    )

    print("Renderizando video final com audio + legendas + efeitos...")
    run_ffmpeg([
        "-i", video_concat,                   # video base
        "-i", audio_file,                     # audio da narracao (começa no segundo 0)
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "1:a",
        "-c:v", "libx264", "-crf", "22", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duracao_total),
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output_file,
    ], description="Vídeo final")

    tamanho = Path(output_file).stat().st_size / (1024 * 1024)
    print(f"\nVideo final: {output_file} ({tamanho:.1f} MB)")
    return output_file


# ── Teste standalone ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        test_file = sys.argv[2] if len(sys.argv) > 2 else ""
        if test_file and Path(test_file).exists():
            dur = get_media_duration(test_file)
            print(f"Duracao de '{test_file}': {dur:.2f}s")
        else:
            print("Use: python montar_video.py --test arquivo.mp4")
