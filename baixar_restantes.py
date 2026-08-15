"""baixar_restantes.py - Baixa as 4 musicas que falharam usando ytsearch."""
import subprocess
from pathlib import Path

MUSICAS_DIR = Path("musicas")
MUSICAS_DIR.mkdir(exist_ok=True)

FAIXAS = [
    ("nuvole_bianche.mp3", "Ludovico Einaudi Nuvole Bianche piano official", 75, 135),
    ("comptine.mp3", "Yann Tiersen Comptine d un autre ete piano Amelie", 10, 70),
    ("cornfield_chase.mp3", "Hans Zimmer Cornfield Chase Interstellar piano", 30, 90),
    ("una_mattina.mp3", "Ludovico Einaudi Una Mattina piano", 40, 100),
]

for nome, busca, inicio, fim in FAIXAS:
    output_final = MUSICAS_DIR / nome
    if output_final.exists():
        print(f"[OK] Ja existe: {nome}")
        continue

    print(f"\n[BAIXANDO] {nome}...")
    tmp_base = MUSICAS_DIR / f"_tmp_{nome.replace('.mp3', '')}"

    cmd_dl = [
        "yt-dlp",
        "--no-playlist",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "-o", str(tmp_base) + ".%(ext)s",
        f"ytsearch1:{busca}",
    ]
    r1 = subprocess.run(cmd_dl, capture_output=True, text=True)
    if r1.returncode != 0:
        print(f"  [ERRO download]: {r1.stderr[-400:]}")
        continue

    candidatos = list(MUSICAS_DIR.glob(f"_tmp_{nome.replace('.mp3', '')}*"))
    if not candidatos:
        print("  [ERRO] Arquivo baixado nao encontrado")
        continue

    arquivo = candidatos[0]
    duracao_corte = fim - inicio

    cmd_cut = [
        "ffmpeg", "-y",
        "-ss", str(inicio),
        "-i", str(arquivo),
        "-t", str(duracao_corte),
        "-af", f"afade=t=in:st=0:d=1,afade=t=out:st={duracao_corte-1}:d=1",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(output_final),
    ]
    r2 = subprocess.run(cmd_cut, capture_output=True, text=True)
    arquivo.unlink(missing_ok=True)

    if r2.returncode != 0:
        print(f"  [ERRO corte]: {r2.stderr[-400:]}")
    else:
        kb = output_final.stat().st_size // 1024
        print(f"  [OK] {nome} ({kb} KB)")

print("\n=== RESULTADO FINAL ===")
mp3s = list(MUSICAS_DIR.glob("*.mp3"))
print(f"Musicas prontas ({len(mp3s)}/8):")
for f in sorted(mp3s):
    print(f"  {f.name}")
