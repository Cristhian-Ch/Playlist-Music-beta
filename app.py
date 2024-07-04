from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from pytube import Playlist, YouTube
import os
from io import BytesIO
import logging
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# Configurar logging para que solo muestre INFO y superiores
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_valid_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and 'youtube.com' in parsed.netloc

def fetch_video_data(video):
    try:
        return {'title': video.title, 'url': video.watch_url}
    except Exception as e:
        logger.error(f"Error fetching video data: {e}")
        return None

@app.route('/')
def index():
    return redirect(url_for('inicio'))

@app.route('/inicio', methods=['GET', 'POST'])
def inicio():
    if request.method == 'POST':
        playlist_url = request.form['playlist_url']
        logger.info(f"Received playlist URL: {playlist_url}")
        if is_valid_url(playlist_url):
            return redirect(url_for('busqueda', playlist_url=playlist_url))
        else:
            flash("URL no válida. Introduzca una URL de YouTube válida.", 'danger')
            return redirect(url_for('inicio'))
    return render_template('inicio.html')

@app.route('/busqueda', methods=['POST'])
def busqueda():
    playlist_url = request.form['playlist_url']
    logger.info(f"Buscando playlist URL: {playlist_url}")
    try:
        playlist = Playlist(playlist_url)
        with ThreadPoolExecutor() as executor:
            videos = list(executor.map(fetch_video_data, playlist.videos))
        # Filtra videos que no se pudieron procesar
        videos = [video for video in videos if video is not None]
        logger.info(f"Videos encontrados: {videos}")
        return render_template('busqueda.html', videos=videos)
    except Exception as e:
        logger.error(f"Error fetching playlist: {e}")
        flash(f"Error al obtener la playlist: {e}", 'danger')
        return redirect(url_for('inicio'))

@app.route('/download', methods=['POST'])
def download():
    video_url = request.form['video_url']
    logger.info(f"Downloading video from URL: {video_url}")
    try:
        yt = YouTube(video_url)
        stream = yt.streams.filter(only_audio=True, abr="160kbps").first()
        if stream is None:
            flash('No se encontró ningún flujo de audio con la tasa de bits especificada.', 'danger')
            return redirect(url_for('inicio'))
        buffer = BytesIO()
        stream.stream_to_buffer(buffer)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{yt.title}.mp3",
            mimetype='audio/mpeg'
        )
    except Exception as e:
        logger.error(f"Error during download: {e}")
        flash(f'Error en la descarga: {e}', 'danger')
    return redirect(url_for('inicio'))

if __name__ == '__main__':
    app.run(debug=False)
