"""
buscar_videos_pexels.py
Busca e baixa vídeos horizontais do Pexels via API.
Aplica hflip (espelhamento) via flag para evitar cópias de direitos.
"""

import os
import random
import sys
from pathlib import Path
from typing import Optional

import requests

# ── Configurações ─────────────────────────────────────────────────────────────
PEXELS_API_BASE = "https://api.pexels.com/videos"
HEADERS_TEMPLATE = {"Authorization": ""}  # Preenchido com env var

# Queries de fallback para garantir que sempre há vídeos disponíveis
QUERIES_FALLBACK = [
    "lonely wolf nature",
    "misty forest morning",
    "dark ocean waves",
    "rain drops forest",
    "empty road fog",
]


# ── Funções auxiliares ────────────────────────────────────────────────────────
def _get_headers() -> dict:
    api_key = os.environ.get("PEXELS_API_KEY", "")
    if not api_key:
        raise ValueError("❌ PEXELS_API_KEY não configurada!")
    return {"Authorization": api_key}


def _escolher_melhor_arquivo(video_files: list) -> Optional[dict]:
    """
    Escolhe o melhor arquivo de vídeo disponível (HD landscape prioritário).
    Prefere resolução HD, width > height (paisagem/horizontal).
    """
    # Filtra apenas arquivos landscape (width > height)
    landscape = [
        f for f in video_files
        if f.get("width", 0) > f.get("height", 0)
        and f.get("file_type", "") == "video/mp4"
        and f.get("width", 0) >= 1280
    ]

    if not landscape:
        # Aceita qualquer mp4 landscape
        landscape = [
            f for f in video_files
            if f.get("width", 0) > f.get("height", 0)
            and f.get("file_type", "") == "video/mp4"
        ]

    if not landscape:
        return None

    # Ordena por qualidade: HD primeiro, depois SD
    qualidade_ordem = {"hd": 0, "sd": 1, "uhd": 2}
    landscape.sort(key=lambda x: qualidade_ordem.get(x.get("quality", ""), 99))

    return landscape[0]


def _download_video(url: str, filepath: str) -> bool:
    """Baixa um vídeo do URL para o filepath indicado."""
    try:
        with requests.get(url, stream=True, timeout=90) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            baixado = 0
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    baixado += len(chunk)
            size_mb = baixado / (1024 * 1024)
            print(f"   📥 {Path(filepath).name} — {size_mb:.1f} MB")
            return True
    except Exception as e:
        print(f"   ❌ Erro ao baixar: {e}")
        # Remove arquivo parcial se existir
        if Path(filepath).exists():
            Path(filepath).unlink()
        return False


def _buscar_por_keyword(keyword: str, per_page: int = 12) -> list:
    """Busca vídeos no Pexels por palavra-chave. Retorna lista de vídeos."""
    params = {
        "query": keyword,
        "per_page": per_page,
        "orientation": "landscape",
        "size": "medium",
    }
    try:
        response = requests.get(
            f"{PEXELS_API_BASE}/search",
            headers=_get_headers(),
            params=params,
            timeout=30,
        )
        if response.status_code == 200:
            videos = response.json().get("videos", [])
            print(f"   🔍 '{keyword}': {len(videos)} vídeos encontrados")
            return videos
        else:
            print(f"   ⚠️ Pexels status {response.status_code} para '{keyword}'")
            return []
    except Exception as e:
        print(f"   ❌ Erro na busca '{keyword}': {e}")
        return []


# ── Função principal ──────────────────────────────────────────────────────────
def buscar_videos(keywords: list, duracao_audio: float, output_dir: str) -> list:
    """
    Busca e baixa vídeos do Pexels compatíveis com o roteiro.

    Args:
        keywords: Lista de palavras-chave em inglês do roteiro
        duracao_audio: Duração da narração em segundos
        output_dir: Pasta onde salvar os vídeos baixados

    Returns:
        Lista de caminhos absolutos dos vídeos baixados
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Quantos clipes precisamos: ~6-8s por clipe, com folga
    clips_necessarios = max(4, int(duracao_audio / 6) + 2)
    print(f"\n🎥 Buscando {clips_necessarios} clipes para cobrir {duracao_audio:.1f}s de áudio...")

    # Combina keywords do roteiro + fallbacks
    todas_keywords = keywords + QUERIES_FALLBACK
    random.shuffle(todas_keywords[:len(keywords)])  # Randomiza apenas as do roteiro

    ids_baixados = set()  # Evita duplicatas
    caminhos_baixados = []

    for keyword in todas_keywords:
        if len(caminhos_baixados) >= clips_necessarios:
            break

        videos = _buscar_por_keyword(keyword, per_page=15)
        random.shuffle(videos)

        for video in videos:
            if len(caminhos_baixados) >= clips_necessarios:
                break

            video_id = video.get("id")
            if video_id in ids_baixados:
                continue

            # Filtra vídeos com duração razoável (4-15 segundos ideal)
            duracao_clip = video.get("duration", 0)
            if duracao_clip < 3:
                continue

            arquivo_video = _escolher_melhor_arquivo(video.get("video_files", []))
            if not arquivo_video:
                continue

            url = arquivo_video.get("link", "")
            if not url:
                continue

            # Nome do arquivo de saída
            filename = output_path / f"clip_{len(caminhos_baixados)+1:02d}_id{video_id}.mp4"

            if _download_video(url, str(filename)):
                ids_baixados.add(video_id)
                caminhos_baixados.append(str(filename))

    print(f"\n✅ {len(caminhos_baixados)} clipes baixados para '{output_dir}'")
    return caminhos_baixados


# ── Execução standalone para teste ───────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        print("🧪 Testando busca de vídeos Pexels...")
        clips = buscar_videos(
            keywords=["lonely wolf nature", "misty forest"],
            duracao_audio=40.0,
            output_dir="test_pexels/",
        )
        print(f"\n📁 Clipes baixados: {clips}")
