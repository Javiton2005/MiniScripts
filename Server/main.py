from dotenv import load_dotenv
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import mysql.connector
import time
import os
import yt_dlp
from os.path import expanduser
import cursor

load_dotenv()


# Conexión a la base de datos remota
conn = mysql.connector.connect(
    host='192.168.0.99',
    user=os.getenv("user_db"),
    password=os.getenv("password_db"),
    database=os.getenv("database")
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


def descarga(song_title: str, output_dir: str = "/mnt/musica"):
    # Asegura que el directorio exista
    os.makedirs(output_dir, exist_ok=True)

    # Configuración de yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch1',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        print(f"Buscando y descargando: {song_title}")
        info = ydl.extract_info(song_title, download=True)
        downloaded_title = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
        print(f"Descargado como: {downloaded_title}")
        return downloaded_title


def descargar_pendientes(output_dir="~/Descargas"):
    carpeta = expanduser(output_dir)

    cursor.execute("SELECT id, titulo, artista FROM spotify WHERE descargada = FALSE")
    canciones = cursor.fetchall()

    for id_cancion, titulo, artista in canciones:
        try:
            nombre_busqueda = f"{titulo} {artista}"
            print(f"Descargando: {nombre_busqueda}")
            descarga(nombre_busqueda, output_dir=carpeta)

            # Marcar como descargada
            cursor.execute("UPDATE spotify SET descargada = TRUE WHERE id = %s", (id_cancion,))
            conn.commit()
            print(f"✅ Marcada como descargada: {titulo} - {artista}")

        except Exception as e:
            print(f"❌ Error al descargar {titulo}: {e}")


while True:
    try:
        playback = sp.current_playback()
        if playback and playback['is_playing']:
            track = playback['item']
            guardar_cancion(track)
            descargar_pendientes()
        else:
            print("No hay reproducción activa.")
    except Exception as e:
        print(f"Error: {e}")
    
    time.sleep(15)
