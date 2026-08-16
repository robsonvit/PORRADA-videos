import json
import os
import requests
import subprocess
import tempfile
from pathlib import Path

# URLs da API do YouTube
YT_TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

PROJETO_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = PROJETO_ROOT / "youtube_credentials.json"


def obter_access_token() -> str:
    # Tenta pegar das variáveis de ambiente primeiro (para GitHub Actions)
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        # Fallback para o arquivo local se não estiver no ambiente
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(f"Arquivo de credenciais não encontrado e variáveis de ambiente não configuradas: {CREDENTIALS_FILE}")
        
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

    # Tenta definir a thumbnail como o primeiro frame do vídeo
    set_thumbnail_from_video(video_id, token, str(video_path_obj))

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  ✅ Vídeo publicado: {url}")
    return url


def set_thumbnail_from_video(video_id: str, token: str, video_path: str):
    print("  🖼️ Extraindo frame inicial para thumbnail...")
    thumb_path = ""
    try:
        # Cria um arquivo temporário para a thumbnail
        fd, thumb_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        
        # Extrai o primeiro frame
        cmd = [
            "ffmpeg", "-y", "-i", video_path, 
            "-ss", "00:00:00", "-vframes", "1", 
            "-q:v", "2", thumb_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        # Envia a thumbnail
        with open(thumb_path, "rb") as f:
            thumb_data = f.read()
            
        print("  ⬆️ Enviando thumbnail para o YouTube...")
        resp = requests.post(
            f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "image/jpeg",
            },
            data=thumb_data,
        )
        if resp.status_code == 200:
            print("  ✓ Thumbnail configurada com sucesso!")
        else:
            print(f"  ⚠️ Aviso: Falha ao configurar thumbnail (Status {resp.status_code}).")
            print(f"  Verifique se o canal está 'Verificado por telefone' para permitir thumbnails personalizadas.")
            
    except Exception as e:
        print(f"  ⚠️ Aviso: Erro ao tentar definir a thumbnail: {e}")
    finally:
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
