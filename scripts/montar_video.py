"""
montar_video.py
Montagem final do vídeo PORRADA usando FFmpeg.

Estrutura do vídeo gerado (1080x1920 vertical):
  ├─ 0:00–0:04  → Clip do Shelby (gancho visual / capa)
  ├─ 0:04+      → Clipes do Pexels (espelhados, cobrem duração do áudio)
  ├─ Áudio      → Narração (pt-BR-AntonioNeural) começa no segundo 0
  ├─ Legendas   → Amarelo dourado, Impact bold, centralizado, palavra a palavra
  ├─ Efeito HDR → curves strong_contrast + saturation + contrast boost
  └─ Efeito Glow→ gblur leve + blend screen (brilho fraco)
"""

import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path


# ── Configurações de vídeo ────────────────────────────────────────────────────
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
SHELBY_CLIP_DURATION = 4.0   # Segundos do clip Shelby no início
MAX_CLIP_DURATION = 8.0       # Duração máxima de cada clipe Pexels
FONT_FILE = "/usr/share/fonts/truetype/anton/Anton-Regular.ttf"  # Instalada via workflow
FONT_SIZE = 82


# ── Utilidades FFmpeg ─────────────────────────────────────────────────────────
def get_media_duration(filepath: str) -> float:
    """Retorna a duração de um arquivo de mídia em segundos via ffprobe."""
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
    """Executa um comando FFmpeg, imprimindo o progresso."""
    if description:
        print(f"  ⚙️  {description}...")
    cmd = ["ffmpeg", "-y"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ❌ FFmpeg erro:\n{result.stderr[-2000:]}")
        raise RuntimeError(f"FFmpeg falhou: {description}")


# ── Geração de legendas ASS ───────────────────────────────────────────────────
def _segundos_para_ass(segundos: float) -> str:
    """Converte segundos para formato de timecode ASS: H:MM:SS.cc"""
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    cs = int((segundos % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def gerar_legendas_ass(word_timings: list, output_file: str, offset: float = 0.0) -> None:
    """
    Gera arquivo de legendas no formato ASS (Advanced SubStation Alpha).
    Estilo: texto amarelo dourado, bold, outline preto, centralizado.

    Args:
        word_timings: Lista de {word, start, duration} do edge-tts
        output_file: Caminho do arquivo .ass de saída
        offset: Offset em segundos (duração do clip Shelby)
    """
    # ── Cabeçalho ASS ─────────────────────────────────────────────────────
    # Cores em formato ASS: &HAABBGGRR (alpha, blue, green, red)
    # Amarelo #FFD700 → R=FF G=D7 B=00 → ASS: &H0000D7FF
    # Preto outline → &H00000000
    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
ScaledBorderAndShadow: yes
WrapStyle: 0
Collisions: Normal

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Anton,{FONT_SIZE},&H0000D7FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,110,1,0,1,5,0,5,60,60,{VIDEO_HEIGHT // 2},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # ── Agrupa palavras em blocos de 2-3 ──────────────────────────────────
    grupos = []
    grupo_atual = []

    for i, timing in enumerate(word_timings):
        grupo_atual.append(timing)

        # Quebra o grupo se: atingiu 3 palavras, ou há pausa maior que 0.8s
        prox_inicio = word_timings[i + 1]["start"] if i < len(word_timings) - 1 else float("inf")
        fim_atual = timing["start"] + timing["duration"]
        pausa = prox_inicio - fim_atual

        if len(grupo_atual) >= 3 or pausa > 0.8:
            grupos.append(grupo_atual)
            grupo_atual = []

    if grupo_atual:
        grupos.append(grupo_atual)

    # ── Gera eventos de diálogo ────────────────────────────────────────────
    eventos = []
    for grupo in grupos:
        inicio = grupo[0]["start"] + offset
        fim = grupo[-1]["start"] + grupo[-1]["duration"] + offset + 0.08
        texto = " ".join(w["word"].upper() for w in grupo)

        # Garante tempo mínimo de exibição (0.4s)
        if fim - inicio < 0.4:
            fim = inicio + 0.4

        evento = (
            f"Dialogue: 0,"
            f"{_segundos_para_ass(inicio)},"
            f"{_segundos_para_ass(fim)},"
            f"Default,,0,0,0,,{texto}"
        )
        eventos.append(evento)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(ass_header)
        f.write("\n".join(eventos))

    print(f"  ✅ {len(eventos)} blocos de legenda gerados (offset: {offset:.1f}s)")


# ── Processamento individual de clipes ───────────────────────────────────────
def processar_clip_vertical(
    input_path: str,
    output_path: str,
    duracao: float,
    aplicar_hflip: bool = False,
) -> None:
    """
    Processa um clipe para formato vertical 1080x1920.
    Faz scale + crop centralizado para preencher sem distorcer.
    """
    hflip_filter = "hflip," if aplicar_hflip else ""
    vf = (
        f"{hflip_filter}"
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
    ], description=f"Processando {Path(input_path).name}")


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

    Args:
        shelby_clips: Lista de paths dos clips Shelby (gancho)
        pexels_clips: Lista de paths dos clips Pexels (corpo)
        audio_file: Path do MP3 da narração
        word_timings: Lista de timings por palavra do edge-tts
        output_file: Path do vídeo final de saída
        work_dir: Diretório temporário para arquivos intermediários

    Returns:
        Path do vídeo final gerado
    """
    work = Path(work_dir)

    # ── 1. Determina duração do áudio ──────────────────────────────────────
    duracao_audio = get_media_duration(audio_file)
    duracao_total = SHELBY_CLIP_DURATION + duracao_audio
    print(f"\n📊 Duração do áudio: {duracao_audio:.1f}s | Total do vídeo: {duracao_total:.1f}s")

    # ── 2. Processa clip Shelby (gancho inicial) ───────────────────────────
    print("\n🎬 Processando clip Shelby (gancho)...")
    shelby_escolhido = random.choice(shelby_clips)
    shelby_dur_orig = get_media_duration(shelby_escolhido)
    shelby_dur = min(SHELBY_CLIP_DURATION, shelby_dur_orig)
    shelby_processed = str(work / "shelby_proc.mp4")

    processar_clip_vertical(
        input_path=shelby_escolhido,
        output_path=shelby_processed,
        duracao=shelby_dur,
        aplicar_hflip=False,  # Shelby não é espelhado
    )

    # ── 3. Processa clips Pexels (espelhados) ─────────────────────────────
    print("\n🎥 Processando clips Pexels...")
    pexels_processed = []
    duracao_acumulada = 0.0
    clip_idx = 0

    while duracao_acumulada < duracao_audio:
        clip_orig = pexels_clips[clip_idx % len(pexels_clips)]
        dur_orig = get_media_duration(clip_orig)
        dur_clip = min(dur_orig, MAX_CLIP_DURATION, duracao_audio - duracao_acumulada)

        if dur_clip < 0.5:
            break

        out_clip = str(work / f"pexels_proc_{clip_idx:02d}.mp4")
        processar_clip_vertical(
            input_path=clip_orig,
            output_path=out_clip,
            duracao=dur_clip,
            aplicar_hflip=True,  # Espelha todos os clips Pexels
        )
        pexels_processed.append(out_clip)
        duracao_acumulada += dur_clip
        clip_idx += 1

    print(f"  ✅ {len(pexels_processed)} clips Pexels processados ({duracao_acumulada:.1f}s)")

    # ── 4. Concatena todos os clips (Shelby + Pexels) ─────────────────────
    print("\n🔗 Concatenando clips...")
    concat_list = str(work / "concat.txt")
    todos_clips = [shelby_processed] + pexels_processed

    with open(concat_list, "w") as f:
        for clip in todos_clips:
            f.write(f"file '{clip}'\n")

    video_concat = str(work / "video_concat.mp4")
    run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        video_concat,
    ], description="Concatenando clips")

    # ── 5. Gera arquivo de legendas ASS ───────────────────────────────────
    print("\n📝 Gerando legendas ASS...")
    subtitles_file = str(work / "legendas.ass")
    gerar_legendas_ass(
        word_timings=word_timings,
        output_file=subtitles_file,
        offset=SHELBY_CLIP_DURATION,  # Legendas começam após o Shelby
    )

    # ── 6. Montagem final: áudio + legendas + efeitos ─────────────────────
    print("\n✨ Aplicando efeitos e gerando vídeo final...")

    # Escapa o path do arquivo ASS para o filtro FFmpeg
    ass_path_escaped = subtitles_file.replace("\\", "/").replace(":", "\\:")

    # Verifica se a fonte Anton está disponível
    font_filter = ""
    if os.path.exists(FONT_FILE):
        font_filter = f"fontsdir=/usr/share/fonts/truetype/anton/,"

    # Filter complex completo:
    # 1. Legendas via ASS
    # 2. Gradação HDR (curves + eq)
    # 3. Efeito glow (gblur + blend screen)
    filter_complex = (
        f"[0:v]"
        f"ass='{ass_path_escaped}',"           # Legendas
        f"curves=preset=strong_contrast,"       # Contraste HDR
        f"eq=saturation=1.40:contrast=1.15:brightness=0.02,"  # Saturação e brilho
        f"split[vmain][vcopy];"                # Split para glow
        f"[vcopy]gblur=sigma=7[vblur];"        # Blur leve
        f"[vmain][vblur]blend=all_mode=screen:all_opacity=0.13[vfinal]"  # Glow fraco
    )

    # Gera áudio com silêncio no início (duração do Shelby)
    audio_delayed = str(work / "audio_delayed.aac")
    run_ffmpeg([
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={SHELBY_CLIP_DURATION}",
        "-i", audio_file,
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[aout]",
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k",
        audio_delayed,
    ], description="Preparando áudio com intro silenciosa")

    # Monta vídeo final
    run_ffmpeg([
        "-i", video_concat,
        "-i", audio_delayed,
        "-filter_complex", filter_complex,
        "-map", "[vfinal]",
        "-map", "1:a",
        "-c:v", "libx264", "-crf", "22", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duracao_total),
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output_file,
    ], description="Renderizando vídeo final")

    tamanho_mb = Path(output_file).stat().st_size / (1024 * 1024)
    print(f"\n✅ Vídeo finalizado: {output_file} ({tamanho_mb:.1f} MB)")
    return output_file


# ── Execução standalone para teste ───────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        print("🧪 Teste de duração de arquivo:")
        test_file = sys.argv[2] if len(sys.argv) > 2 else "test.mp4"
        if Path(test_file).exists():
            dur = get_media_duration(test_file)
            print(f"  Duração de '{test_file}': {dur:.2f}s")
        else:
            print(f"  Arquivo '{test_file}' não encontrado.")
