"""
enviar_telegram.py
Envia o vídeo finalizado para um chat/canal do Telegram via Bot API.
Suporta vídeos de até 50MB (limite da Bot API via HTTP).
"""

import os
import sys
from pathlib import Path

import requests


def enviar_video_telegram(video_path: str, caption: str) -> bool:
    """
    Envia um vídeo MP4 para o Telegram via Bot API.

    Args:
        video_path: Caminho absoluto do arquivo .mp4
        caption: Texto da legenda (título + hashtags)

    Returns:
        True se enviado com sucesso, False caso contrário
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not bot_token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN não configurado!")
    if not chat_id:
        raise ValueError("❌ TELEGRAM_CHAT_ID não configurado!")

    video_file = Path(video_path)
    if not video_file.exists():
        raise FileNotFoundError(f"❌ Arquivo de vídeo não encontrado: {video_path}")

    tamanho_mb = video_file.stat().st_size / (1024 * 1024)
    print(f"📨 Enviando vídeo ao Telegram ({tamanho_mb:.1f} MB)...")
    print(f"   📺 Chat ID: {chat_id}")

    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"

    with open(video_path, "rb") as video_f:
        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "supports_streaming": "true",
                "width": "1080",
                "height": "1920",
            },
            files={"video": (video_file.name, video_f, "video/mp4")},
            timeout=300,  # 5 minutos de timeout para vídeos grandes
        )

    if response.status_code == 200:
        result = response.json()
        msg_id = result.get("result", {}).get("message_id", "?")
        print(f"✅ Vídeo enviado com sucesso! Message ID: {msg_id}")
        return True
    else:
        print(f"❌ Erro ao enviar: HTTP {response.status_code}")
        print(f"   Resposta: {response.text[:500]}")
        response.raise_for_status()
        return False


def enviar_mensagem_telegram(texto: str) -> bool:
    """Envia uma mensagem de texto simples ao Telegram (útil para status/erros)."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "HTML",
        },
        timeout=30,
    )
    return response.status_code == 200


# ── Execução standalone para teste ───────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        print("🧪 Testando conexão com Telegram...")
        ok = enviar_mensagem_telegram(
            "🎬 <b>PORRADA Bot</b> está online e pronto para enviar vídeos! ✅"
        )
        if ok:
            print("✅ Mensagem de teste enviada com sucesso!")
        else:
            print("❌ Falha ao enviar mensagem de teste")
