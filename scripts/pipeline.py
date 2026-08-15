"""
pipeline.py
Orquestrador principal do pipeline de criação de Vídeos PORRADA.

Fluxo completo:
  1. Escolhe tema único (sem repetir 10 rodadas)
  2. Gera roteiro via Grok API
  3. Sintetiza narração com edge-tts (pt-BR-AntonioNeural)
  4. Baixa clipes compatíveis do Pexels
  5. Monta vídeo final 1080x1920 com FFmpeg
  6. Envia ao Telegram
  7. Atualiza controle de temas usados
"""

import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

# ── Adiciona o diretório de scripts ao path ───────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from gerar_roteiro import escolher_tema, gerar_roteiro, salvar_tema_usado
from gerar_voz import gerar_voz, calcular_duracao_audio
from buscar_videos_pexels import buscar_videos
from montar_video import montar_video, get_media_duration, SHELBY_CLIP_DURATION
from enviar_telegram import enviar_video_telegram, enviar_mensagem_telegram
from enviar_youtube import enviar_video_youtube

# ── Paths do projeto ──────────────────────────────────────────────────────────
PROJETO_ROOT = Path(__file__).parent.parent
SHELBY_DIR = PROJETO_ROOT / "VÍDEOS DO SHELBY"
MUSICAS_DIR = PROJETO_ROOT / "musicas"
OUTPUT_DIR = PROJETO_ROOT / "output"


def executar_pipeline(numero: int = 1) -> bool:
    """
    Executa o pipeline completo de criação de um vídeo PORRADA.

    Args:
        numero: Número sequencial do vídeo nesta rodada (para logging)

    Returns:
        True se o pipeline concluiu com sucesso
    """
    print(f"\n{'='*60}")
    print(f"  🎬 VÍDEO PORRADA #{numero}")
    print(f"{'='*60}\n")

    # Cria diretório de trabalho temporário
    work_dir = Path(tempfile.mkdtemp(prefix="porrada_"))
    print(f"📁 Diretório de trabalho: {work_dir}")

    try:
        # ── Passo 1: Escolhe tema e gera roteiro ──────────────────────────
        print("\n📝 [1/6] Gerando roteiro via Grok...")
        tema = escolher_tema()
        roteiro = gerar_roteiro(tema)

        # ── Passo 2: Sintetiza voz ────────────────────────────────────────
        print("\n🎙️ [2/6] Sintetizando narração com edge-tts...")
        audio_file = str(work_dir / "narration.mp3")
        timing_file = str(work_dir / "timings.json")
        word_timings = gerar_voz(
            texto=roteiro["roteiro_fala"],
            output_audio=audio_file,
            output_timing=timing_file,
        )
        duracao_audio = calcular_duracao_audio(timing_file)
        print(f"  📊 Duração da narração: {duracao_audio:.1f}s")

        # ── Passo 3: Baixa vídeos Pexels ──────────────────────────────────
        print("\n🎥 [3/6] Buscando vídeos Pexels...")
        pexels_dir = str(work_dir / "pexels_clips")
        pexels_clips = buscar_videos(
            keywords=roteiro["palavras_chave_pexels"],
            duracao_audio=duracao_audio,
            output_dir=pexels_dir,
        )

        if not pexels_clips:
            raise RuntimeError("❌ Nenhum clip Pexels foi baixado!")

        # ── Passo 4: Coleta clips Shelby ──────────────────────────────────────
        print("\n[4/6] Coletando clips Shelby...")
        shelby_clips = sorted(SHELBY_DIR.glob("*.mp4"))
        if not shelby_clips:
            raise RuntimeError(f"Nenhum clip encontrado em: {SHELBY_DIR}")
        print(f"  {len(shelby_clips)} clips Shelby disponiveis")

        # ── Passo 5: Monta o vídeo final ──────────────────────────────────────
        # word_timings vai direto para montar_video que gera as legendas internamente
        # Audio começa no segundo 0, legendas aparecem desde o segundo 0
        print("\n[5/6] Montando video final...")

        titulo_seguro = (
            roteiro["titulo"]
            .replace(" ", "_")
            .replace("/", "-")
            .replace(":", "")
            [:50]
        )
        output_file = str(work_dir / f"PORRADA_{titulo_seguro}.mp4")

        # Loga se musicas estao disponiveis
        musicas_disponíveis = list(MUSICAS_DIR.glob("*.mp3")) if MUSICAS_DIR.exists() else []
        if musicas_disponíveis:
            print(f"  {len(musicas_disponíveis)} musica(s) de fundo disponivel(is) em: {MUSICAS_DIR}")
        else:
            print(f"  [AVISO] Pasta musicas/ nao encontrada ou vazia — video sem fundo musical.")

        montar_video(
            shelby_clips=[str(c) for c in shelby_clips],
            pexels_clips=pexels_clips,
            audio_file=audio_file,
            word_timings=word_timings,
            output_file=output_file,
            work_dir=str(work_dir),
            musicas_dir=str(MUSICAS_DIR) if MUSICAS_DIR.exists() else "",
        )

        # Copia para pasta output permanente
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_final = str(OUTPUT_DIR / Path(output_file).name)
        shutil.copy2(output_file, output_final)

        # ── Passo 6: Envia ao Telegram e YouTube ──────────────────────────
        print("\n📨 [6/7] Enviando ao Telegram...")
        caption = (
            f"🔥 <b>{roteiro['titulo']}</b>\n\n"
            f"{roteiro['hashtags']}"
        )
        enviar_video_telegram(output_final, caption)

        print("\n▶️ [7/7] Enviando ao YouTube (Shorts)...")
        yt_titulo = f"{roteiro['titulo'][:85]} #shorts"
        yt_desc = f"{roteiro['titulo']}\n\n{roteiro['hashtags']}"
        yt_tags = [tag.strip("#") for tag in roteiro['hashtags'].split() if tag.startswith("#")]
        
        try:
            yt_url = enviar_video_youtube(
                video_path=output_final,
                titulo=yt_titulo,
                descricao=yt_desc,
                tags=yt_tags
            )
            print(f"  📺 Vídeo postado no YouTube: {yt_url}")
            enviar_mensagem_telegram(f"✅ <b>Vídeo postado no YouTube!</b>\n{yt_url}")
        except Exception as yt_err:
            print(f"  ❌ Erro ao enviar para o YouTube: {yt_err}")
            enviar_mensagem_telegram(f"⚠️ Erro ao postar no YouTube:\n<code>{yt_err}</code>")

        # ── Salva o tema usado ────────────────────────────────────────────
        salvar_tema_usado(tema)

        print(f"\n{'='*60}")
        print(f"  ✅ VÍDEO #{numero} CONCLUÍDO COM SUCESSO!")
        print(f"  📁 Salvo em: {output_final}")
        print(f"{'='*60}\n")
        return True

    except Exception as e:
        print(f"\n❌ ERRO no pipeline do vídeo #{numero}:")
        traceback.print_exc()
        # Notifica o Telegram sobre o erro
        enviar_mensagem_telegram(
            f"⚠️ <b>PORRADA Bot</b>\nErro ao gerar vídeo #{numero}:\n<code>{str(e)[:300]}</code>"
        )
        return False

    finally:
        # Limpa arquivos temporários
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
            print(f"🧹 Temporários limpos: {work_dir}")


# ── Ponto de entrada principal ────────────────────────────────────────────────
if __name__ == "__main__":
    # Determina quantos vídeos gerar
    num_videos = 1
    if len(sys.argv) > 1:
        try:
            num_videos = int(sys.argv[1])
            num_videos = max(1, min(10, num_videos))  # Limita entre 1 e 10
        except ValueError:
            pass

    print(f"\n🚀 INICIANDO PIPELINE — {num_videos} vídeo(s) a gerar")

    sucessos = 0
    falhas = 0

    for i in range(1, num_videos + 1):
        ok = executar_pipeline(numero=i)
        if ok:
            sucessos += 1
        else:
            falhas += 1

    print(f"\n📊 RESUMO FINAL: {sucessos} sucesso(s), {falhas} falha(s)")

    if falhas > 0:
        sys.exit(1)
