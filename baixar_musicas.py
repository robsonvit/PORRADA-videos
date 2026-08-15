# -*- coding: utf-8 -*-
"""
baixar_musicas.py -- Baixa e corta os 8 trechos de musicas de fundo para os videos PORRADA.

Execute uma unica vez na sua maquina:
    python baixar_musicas.py

Requer: yt-dlp e ffmpeg instalados.
"""

import subprocess
import sys
from pathlib import Path

MUSICAS_DIR = Path(__file__).parent / "musicas"

# (nome_arquivo, url_youtube, inicio_segundos, fim_segundos)
FAIXAS = [
    (
        "nuvole_bianche.mp3",
        "https://www.youtube.com/watch?v=sR2W2scFS4Y",
        75,   # 01:15
        135,  # 02:15
    ),
    (
        "comptine.mp3",
        "https://www.youtube.com/watch?v=PaXKf0JEzEA",
        10,   # 00:10
        70,   # 01:10
    ),
    (
        "nature_daylight.mp3",
        "https://www.youtube.com/watch?v=b_YHE4Sx-08",
        60,   # 01:00
        120,  # 02:00
    ),
    (
        "cornfield_chase.mp3",
        "https://www.youtube.com/watch?v=hHlpIBvaZvc",
        30,   # 00:30
        90,   # 01:30
    ),
    (
        "time.mp3",
        "https://www.youtube.com/watch?v=RxabLA7UQ9k",  # será atualizado se necessário
        80,   # 01:20
        140,  # 02:20
    ),
    (
        "una_mattina.mp3",
        "https://www.youtube.com/watch?v=-8X_aMT5z0A",
        40,   # 00:40
        100,  # 01:40
    ),
    (
        "gymnopedie.mp3",
        "https://www.youtube.com/watch?v=bLbxSHFHPuk",
        0,    # 00:00
        60,   # 01:00
    ),
    (
        "the_departure.mp3",
        "https://www.youtube.com/watch?v=8us4hHS9ZSA",
        20,   # 00:20
        80,   # 01:20
    ),
]


def segundos_para_hhmmss(s: int) -> str:
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def baixar_e_cortar(nome: str, url: str, inicio: int, fim: int) -> bool:
    output_final = MUSICAS_DIR / nome
    if output_final.exists():
        print(f"  [OK] Ja existe: {nome} -- pulando.")
        return True

    tmp_audio = MUSICAS_DIR / f"_tmp_{nome}"
    duracao = fim - inicio

    print(f"\n[BAIXANDO] {nome}  [{segundos_para_hhmmss(inicio)} -> {segundos_para_hhmmss(fim)}]")

    # 1. Baixa apenas o áudio em formato bestaudio via yt-dlp
    cmd_download = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "-o", str(tmp_audio.with_suffix("")) + ".%(ext)s",
        url,
    ]
    result = subprocess.run(cmd_download, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERRO] Erro ao baixar {nome}: {result.stderr[-500:]}")
        return False

    # Localiza o arquivo baixado (pode ser .mp3 ou .webm convertido)
    candidatos = list(MUSICAS_DIR.glob(f"_tmp_{nome.replace('.mp3', '')}*"))
    if not candidatos:
        print(f"  [ERRO] Arquivo baixado nao encontrado para {nome}")
        return False

    arquivo_baixado = candidatos[0]

    # 2. Corta o trecho com ffmpeg: -ss antes de -i = seek rápido
    cmd_cortar = [
        "ffmpeg", "-y",
        "-ss", str(inicio),
        "-i", str(arquivo_baixado),
        "-t", str(duracao),
        "-af", "afade=t=in:st=0:d=1,afade=t=out:st=" + str(duracao - 1) + ":d=1",  # fade in/out 1s
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(output_final),
    ]
    result2 = subprocess.run(cmd_cortar, capture_output=True, text=True)

    # Limpa tmp
    arquivo_baixado.unlink(missing_ok=True)

    if result2.returncode != 0:
        print(f"  [ERRO] Erro ao cortar {nome}: {result2.stderr[-500:]}")
        return False

    size_kb = output_final.stat().st_size // 1024
    print(f"  [OK] Salvo: {nome} ({size_kb} KB)")
    return True


def main():
    MUSICAS_DIR.mkdir(exist_ok=True)
    print(f"Pasta de musicas: {MUSICAS_DIR}")

    sucessos = 0
    falhas = []

    for nome, url, inicio, fim in FAIXAS:
        ok = baixar_e_cortar(nome, url, inicio, fim)
        if ok:
            sucessos += 1
        else:
            falhas.append(nome)

    print(f"\n{'='*50}")
    print(f"[RESULTADO] {sucessos}/{len(FAIXAS)} musicas baixadas com sucesso")
    if falhas:
        print(f"[ERRO] Falhas: {', '.join(falhas)}")
        sys.exit(1)
    else:
        print("Todas as musicas prontas! Commite a pasta musicas/ no GitHub.")


if __name__ == "__main__":
    main()
