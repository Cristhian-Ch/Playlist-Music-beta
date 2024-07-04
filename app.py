from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from pytube import Playlist, YouTube
import os
from io import BytesIO
import logging
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import boto3

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# Configurar logging para que solo muestre INFO y superiores
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar boto3 para S3
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION')
)
bucket_name = os.environ.get('AWS_STORAGE_BUCKET_NAME')

def is_valid_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and 'youtube.com' in parsed.netloc

def fetch_video_data(video):
    try:
        return {'title': video.title, 'url': video.watch_url}
    except Exception as e:
        logger.error(f"Error fetching video data: {e}")
        return None

def upload_to_s3(buffer, filename):
    try:
        s3_client.upload_fileobj(buffer, bucket_name, filename)
        file_url = f"https://{bucket_name}.s3.amazonaws.com/{filename}"
        return file_url
    except Exception as e:
        logger.error(f"Error uploading to S3: {e}")
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
        stream = yt.streams.filter(only_audio=True, abr="320kbps").first()
        if stream is None:
            flash('No se encontró ningún flujo de audio con la tasa de bits especificada.', 'danger')
            return redirect(url_for('inicio'))
        buffer = BytesIO()
        stream.stream_to_buffer(buffer)
        buffer.seek(0)
        filename = f"{yt.title}.mp3"
        file_url = upload_to_s3(buffer, filename)
        if file_url:
            return jsonify({"url": file_url})
        else:
            flash('Error subiendo el archivo a S3.', 'danger')
    except Exception as e:
        logger.error(f"Error during download: {e}")
        flash(f'Error en la descarga: {e}', 'danger')
    return redirect(url_for('inicio'))

if __name__ == '__main__':
    app.run(debug=False)
