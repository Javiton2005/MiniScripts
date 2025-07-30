from dotenv import load_dotenv
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import mysql.connector
import time
import os
from yt_dlp import YoutubeDL
import cursor
import descargar
import asyncio
import threading

load_dotenv()
path = os.getenv("PATH_DESCARGA")

# Conexión a la base de datos remota
conn = mysql.connector.connect(
    host='192.168.0.99',
    user=os.getenv("USER_DB"),
    password=os.getenv("PASSWORD_DB"),
    database=os.getenv("DATABASE")
)
cursor = conn.cursor()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    redirect_uri='http://127.0.0.1:8888/callback',
    scope='user-read-playback-state',
    open_browser=False,
    cache_path=os.path.expanduser('~/token.json')
))


def marcar_como_descargada(id_cancion, youtube_url):
    cursor.execute(
        "UPDATE spotify SET descargada = %s, youtube_url = %s WHERE id = %s",
        (True, youtube_url, id_cancion)
    )
    conn.commit()
    print(f"✔️ Marcada como descargada: {id_cancion}")


def progress_handler(status):
    """if 'percent' in status:
        print(f"Progreso: {status['percent']:.1f}% - {status['status']}")
    else:
        print(f"Estado: {status['status']}")
    """

def buscar_en_youtube(nombre_cancion, id_cancion):
    query = f"ytsearch1:{nombre_cancion}"
    with YoutubeDL({'quiet': True}) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info and info['entries']:
                url = info['entries'][0]['webpage_url']
                asyncio.run(descargar.download_video_as_mp3(
                    url,
                    path, 
                    progress_callback=progress_handler
                ))
                marcar_como_descargada(id_cancion, url)
                return url
        except Exception as e:
            print(f"Error buscando en YouTube: {e}")
    return None


def procesar_descargas():
    while True:
        try:
            cursor.execute("SELECT id, titulo, artista FROM spotify WHERE descargada = FALSE")
            canciones_pendientes = cursor.fetchall()

            for id_cancion, titulo, artista in canciones_pendientes:
                nombre_cancion = f"{titulo} {artista}"
                print(f"🔍 Buscando y descargando: {nombre_cancion}")
                buscar_en_youtube(nombre_cancion, id_cancion)

            time.sleep(10)  # Esperar antes de revisar de nuevo
        except Exception as e:
            print(f"❌ Error en el hilo de descargas: {e}")
            time.sleep(10)

# Iniciar hilo de descargas
hilo_descargas = threading.Thread(target=procesar_descargas, daemon=True)
hilo_descargas.start()


def guardar_cancion(track):
    id_cancion = track['id']
    titulo = track['name']
    artista = ', '.join([artist['name'] for artist in track['artists']])
    duracion_ms = track['duration_ms']

    cursor.execute("SELECT id, descargada FROM spotify WHERE id = %s", (id_cancion,))
    result = cursor.fetchone()

    if result is None:
        cursor.execute(
            "INSERT INTO spotify (id, titulo, artista, duracion_ms, descargada) VALUES (%s, %s, %s, %s, %s)",
            (id_cancion, titulo, artista, duracion_ms, False)
        )
        conn.commit()
        print(f"Guardado (pendiente descarga): {titulo} - {artista}")
    else:
        print(f"Ya registrado: {titulo} - {artista}")


while True:
    try:
        playback = sp.current_playback()
        if playback and playback['is_playing']:
            track = playback['item']
            guardar_cancion(track)
        else:
            print("No hay reproducción activa.")
    except Exception as e:
        print(f"Error: {e}")
    
    time.sleep(15)