import json
import os
import requests
from pathlib import Path

# URLs da API do YouTube
YT_TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

PROJETO_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = PROJETO_ROOT / "youtube_credentials.json"


def obter_access_token() -> str:
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(f"Arquivo de credenciais não encontrado: {CREDENTIALS_FILE}")
    
    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        creds = json.load(f)
        
    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    refresh_token = creds.get("refresh_token")
    
    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("Credenciais incompletas no arquivo youtube_credentials.json")

    resp = requests.post(YT_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError(f"Falha ao obter access_token: {resp.text}")
    
    return token


def enviar_video_youtube(video_path: str, titulo: str, descricao: str, tags: list = None) -> str:
    """Faz upload do vídeo usando upload resumível para o YouTube."""
    if tags is None:
        tags = []
        
    print(f"\n[YouTube] Iniciando upload do vídeo: {titulo}")
    
    token = obter_access_token()
    video_path_obj = Path(video_path)
    file_size = video_path_obj.stat().st_size

    # Configuração de metadata para o vídeo
    headers_init = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(file_size),
    }

    metadata = {
        "snippet": {
            "title": titulo,
            "description": descricao,
            "tags": tags,
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    # Iniciar upload resumível
    init_resp = requests.post(
        f"{YT_UPLOAD_URL}?uploadType=resumable&part=snippet,status",
        headers=headers_init,
        json=metadata,
    )
    init_resp.raise_for_status()
    upload_url = init_resp.headers["Location"]
    print("  ✓ URL de upload obtida.")

    # Fazer upload em chunks (10 MB por vez)
    CHUNK_SIZE = 10 * 1024 * 1024
    video_id = None

    with open(video_path_obj, "rb") as f:
        offset = 0
        while offset < file_size:
            chunk = f.read(CHUNK_SIZE)
            end = offset + len(chunk) - 1
            headers_chunk = {
                "Authorization": f"Bearer {token}",
                "Content-Range": f"bytes {offset}-{end}/{file_size}",
                "Content-Type": "video/mp4",
            }
            chunk_resp = requests.put(upload_url, headers=headers_chunk, data=chunk)

            if chunk_resp.status_code in (200, 201):
                video_id = chunk_resp.json().get("id")
                print(f"  ✓ Upload completo! Video ID: {video_id}")
                break
            elif chunk_resp.status_code == 308:
                # Continuar o upload
                rng = chunk_resp.headers.get("Range", "")
                if rng:
                    offset = int(rng.split("-")[1]) + 1
                else:
                    offset += len(chunk)
                pct = int(offset * 100 / file_size)
                print(f"  Enviando... {pct}%", end="\r")
            else:
                raise Exception(f"Erro no upload: {chunk_resp.status_code} {chunk_resp.text}")

    if not video_id:
        raise Exception("Upload falhou – video_id não retornado.")

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  ✅ Vídeo publicado: {url}")
    return url
