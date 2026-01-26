#!/usr/bin/env python3
"""
Script para descargar playlists de YouTube
Requiere: pip install yt-dlp
"""

import os
import sys
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp no está instalado.")
    print("Instálalo con: pip install yt-dlp")
    sys.exit(1)


def descargar_playlist(url_playlist, carpeta_destino="Descargas_YouTube"):
    """
    Descarga una playlist completa de YouTube
    
    Args:
        url_playlist: URL de la playlist de YouTube
        carpeta_destino: Carpeta donde se guardarán los videos
    """
    
    # Crear carpeta de destino si no existe
    Path(carpeta_destino).mkdir(parents=True, exist_ok=True)
    
    # Configuración de descarga
    opciones = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(carpeta_destino, '%(playlist)s', '%(playlist_index)s - %(title)s.%(ext)s'),
        'ignoreerrors': True,  # Continuar si hay errores
        'no_warnings': False,
        'extract_flat': False,
        'writethumbnail': False,  # Cambiar a True si quieres las miniaturas
        'writesubtitles': False,  # Cambiar a True si quieres subtítulos
        'writeautomaticsub': False,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'progress_hooks': [mostrar_progreso],
    }
    
    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            print(f"\n📥 Descargando playlist: {url_playlist}")
            print(f"📁 Destino: {carpeta_destino}\n")
            
            # Obtener información de la playlist
            info = ydl.extract_info(url_playlist, download=False)
            if 'entries' in info:
                print(f"✓ Playlist encontrada: {info.get('title', 'Sin título')}")
                print(f"✓ Total de videos: {len(info['entries'])}\n")
            
            # Descargar
            ydl.download([url_playlist])
            print("\n✅ ¡Descarga completada!")
            
    except Exception as e:
        print(f"\n❌ Error durante la descarga: {str(e)}")
        return False
    
    return True


def mostrar_progreso(d):
    """Callback para mostrar el progreso de descarga"""
    if d['status'] == 'downloading':
        porcentaje = d.get('_percent_str', 'N/A')
        velocidad = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        print(f"\rDescargando: {porcentaje} | Velocidad: {velocidad} | ETA: {eta}", end='')
    elif d['status'] == 'finished':
        print(f"\n✓ Descarga finalizada: {d['filename']}")


def descargar_solo_audio(url_playlist, carpeta_destino="Audio_YouTube"):
    """
    Descarga solo el audio de una playlist (formato MP3)
    
    Args:
        url_playlist: URL de la playlist de YouTube
        carpeta_destino: Carpeta donde se guardarán los audios
    """
    
    Path(carpeta_destino).mkdir(parents=True, exist_ok=True)
    
    opciones = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(carpeta_destino, '%(playlist)s', '%(playlist_index)s - %(title)s.%(ext)s'),
        'ignoreerrors': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'progress_hooks': [mostrar_progreso],
    }
    
    try:
        with yt_dlp.YoutubeDL(opciones) as ydl:
            print(f"\n🎵 Descargando audio de playlist: {url_playlist}")
            print(f"📁 Destino: {carpeta_destino}\n")
            
            info = ydl.extract_info(url_playlist, download=False)
            if 'entries' in info:
                print(f"✓ Playlist: {info.get('title', 'Sin título')}")
                print(f"✓ Total: {len(info['entries'])} audios\n")
            
            ydl.download([url_playlist])
            print("\n✅ ¡Descarga de audio completada!")
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False
    
    return True


def main():
    """Función principal"""
    print("=" * 60)
    print("   DESCARGADOR DE PLAYLISTS DE YOUTUBE")
    print("=" * 60)
    
    # Menú de opciones
    print("\n¿Qué deseas descargar?")
    print("1. Video completo (MP4)")
    print("2. Solo audio (MP3)")
    
    opcion = input("\nElige una opción (1 o 2): ").strip()
    
    # Solicitar URL de la playlist
    url = input("\nPega la URL de la playlist de YouTube: ").strip()
    
    if not url:
        print("❌ Error: Debes proporcionar una URL")
        return
    
    # Solicitar carpeta de destino (opcional)
    carpeta = input("\nCarpeta de destino (Enter para usar la predeterminada): ").strip()
    
    # Ejecutar descarga según la opción elegida
    if opcion == "1":
        carpeta = carpeta or "Descargas_YouTube"
        descargar_playlist(url, carpeta)
    elif opcion == "2":
        carpeta = carpeta or "Audio_YouTube"
        descargar_solo_audio(url, carpeta)
    else:
        print("❌ Opción no válida")


if __name__ == "__main__":
    main()