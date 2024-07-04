from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from pytube import Playlist, YouTube
import os
import logging
from urllib.parse import urlparse
from io import BytesIO
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
        videos = [{'title': video.title, 'url': video.watch_url} for video in playlist.videos]
        logger.info(f"Videos encontrados: {videos}")
        return render_template('busqueda.html', videos=videos)
    except Exception as e:
        logger.error(f"Error fetching playlist: {e}")
        flash(f"Error al obtener la playlist: {e}", 'danger')
        return redirect(url_for('inicio'))

@app.route('/generate-presigned-url', methods=['POST'])
def generate_presigned_url():
    video_url = request.form['video_url']
    logger.info(f"Generating presigned URL for video: {video_url}")
    try:
        yt = YouTube(video_url)
        stream = yt.streams.filter(only_audio=True, abr="320kbps").first()
        if stream is None:
            return jsonify({'error': 'No se encontró ningún flujo de audio con la tasa de bits especificada.'}), 400
        
        filename = f"{yt.title}.mp3"
        presigned_url = s3_client.generate_presigned_url('put_object',
                                                         Params={'Bucket': bucket_name, 'Key': filename},
                                                         ExpiresIn=3600)
        return jsonify({"presigned_url": presigned_url, "filename": filename})
    except Exception as e:
        logger.error(f"Error generating presigned URL: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    video_url = request.form['video_url']
    logger.info(f"Downloading video from URL: {video_url}")
    try:
        yt = YouTube(video_url)
        stream = yt.streams.filter(only_audio=True, abr="320kbps").first()
        if stream is None:
            return jsonify({'error': 'No se encontró ningún flujo de audio con la tasa de bits especificada.'}), 400

        buffer = BytesIO()
        stream.stream_to_buffer(buffer)
        buffer.seek(0)
        file_data = buffer.read()

        return jsonify({"file": file_data, "size": len(file_data)})
    except Exception as e:
        logger.error(f"Error during download: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False)
