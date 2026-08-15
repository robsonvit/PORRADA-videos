"""baixar_faltantes.py - Tenta multiplos IDs para as 2 musicas que faltam."""
import subprocess
from pathlib import Path

MUSICAS_DIR = Path("musicas")

def tentar_baixar(nome, ids_candidatos, inicio, fim):
    output_final = MUSICAS_DIR / nome
    if output_final.exists():
        print(f"[OK] Ja existe: {nome}")
        return True

    duracao_corte = fim - inicio

    for vid_id in ids_candidatos:
        url = f"https://www.youtube.com/watch?v={vid_id}"
        print(f"  Tentando ID: {vid_id}...")
        tmp = MUSICAS_DIR / f"_tmp_{nome.replace('.mp3','')}"

        cmd_dl = [
            "yt-dlp", "--no-playlist",
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "-o", str(tmp) + ".%(ext)s",
            url,
        ]
        r1 = subprocess.run(cmd_dl, capture_output=True, text=True)
        if r1.returncode != 0:
            print(f"    [FALHOU] {r1.stderr.strip()[-200:]}")
            continue

        candidatos = list(MUSICAS_DIR.glob(f"_tmp_{nome.replace('.mp3','')}*"))
        if not candidatos:
            print("    [FALHOU] arquivo nao encontrado")
            continue

        arquivo = candidatos[0]
        cmd_cut = [
            "ffmpeg", "-y",
            "-ss", str(inicio), "-i", str(arquivo),
            "-t", str(duracao_corte),
            "-af", f"afade=t=in:st=0:d=1,afade=t=out:st={duracao_corte-1}:d=1",
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(output_final),
        ]
        r2 = subprocess.run(cmd_cut, capture_output=True, text=True)
        arquivo.unlink(missing_ok=True)

        if r2.returncode != 0:
            print(f"    [FALHOU corte] {r2.stderr[-200:]}")
            continue

        kb = output_final.stat().st_size // 1024
        print(f"  [OK] {nome} ({kb} KB) via {vid_id}")
        return True

    print(f"[ERRO] Todos os IDs falharam para {nome}")
    return False


# Cornfield Chase - tentando IDs alternativos
print("\n=== cornfield_chase.mp3 ===")
tentar_baixar(
    "cornfield_chase.mp3",
    ["5zsBVm4qK_A", "yqYVu--uvQo", "4VXErA63_eg"],
    30, 90
)

# Una Mattina - tentando IDs alternativos
print("\n=== una_mattina.mp3 ===")
tentar_baixar(
    "una_mattina.mp3",
    ["tSyrgAbFE1k", "MPlkHxFA-Qg", "PYj3_ev_ZMI"],
    40, 100
)

print("\n=== RESULTADO FINAL ===")
mp3s = sorted(MUSICAS_DIR.glob("*.mp3"))
print(f"Musicas prontas ({len(mp3s)}/8):")
for f in mp3s:
    print(f"  {f.name}")
