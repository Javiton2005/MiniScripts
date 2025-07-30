import os
import yt_dlp
import logging
import multiprocessing
import asyncio
from dl_formats import get_format, get_opts

log = logging.getLogger('ytdl')

class SimpleDownloader:
    def __init__(self, download_dir, temp_dir=None, output_template="%(title)s.%(ext)s"):
        self.download_dir = download_dir
        self.temp_dir = temp_dir or os.path.join(download_dir, "temp")
        self.output_template = output_template
        # Configuración fija para MP3 en mejor calidad
        self.format = "bestaudio/best"  # Mejor audio disponible
        self.quality = "best"
        
        # Opciones específicas para MP3
        self.ytdl_opts = {
            'format': self.format,
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '0',  # Mejor calidad (0 = mejor, 9 = peor)
            'embed_subs': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
    
    def _download_sync(self, url, status_queue):
        """Función de descarga síncrona que se ejecuta en un proceso separado"""
        log.info(f"Starting MP3 download for: {url}")
        try:
            def put_status(st):
                status_queue.put({k: v for k, v in st.items() if k in (
                    'tmpfilename',
                    'filename',
                    'status',
                    'msg',
                    'total_bytes',
                    'total_bytes_estimate',
                    'downloaded_bytes',
                    'speed',
                    'eta',
                )})

            def put_status_postprocessor(d):
                if d['postprocessor'] == 'MoveFiles' and d['status'] == 'finished':
                    if '__finaldir' in d['info_dict']:
                        filename = os.path.join(d['info_dict']['__finaldir'], 
                                             os.path.basename(d['info_dict']['filepath']))
                    else:
                        filename = d['info_dict']['filepath']
                    status_queue.put({'status': 'finished', 'filename': filename})

            # Configuración de yt-dlp para MP3
            ydl_params = {
                'quiet': True,
                'no_color': True,
                'paths': {"home": self.download_dir, "temp": self.temp_dir},
                'outtmpl': {"default": self.output_template},
                'format': self.format,
                'socket_timeout': 30,
                'ignore_no_formats_error': True,
                'progress_hooks': [put_status],
                'postprocessor_hooks': [put_status_postprocessor],
                **self.ytdl_opts,
            }

            ret = yt_dlp.YoutubeDL(params=ydl_params).download([url])
            status_queue.put({'status': 'finished' if ret == 0 else 'error'})
            log.info(f"Finished MP3 download for: {url}")
            return ret
            
        except yt_dlp.utils.YoutubeDLError as exc:
            log.error(f"Download error for {url}: {str(exc)}")
            status_queue.put({'status': 'error', 'msg': str(exc)})
            return 1
    
    async def download_mp3(self, url, callback=None):
        """
        Descarga un video como MP3 en la mejor calidad disponible
        
        Args:
            url (str): URL del video a descargar
            callback (callable, optional): Función que recibe actualizaciones de estado
                Ejemplo: callback({'status': 'downloading', 'percent': 50.0, 'speed': 1024000})
        
        Returns:
            dict: {'status': 'finished'/'error', 'filename': '...', 'msg': '...'}
        """
        log.info(f"Preparing MP3 download for: {url}")
        
        # Crear directorios si no existen
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Configurar multiprocessing
        manager = multiprocessing.Manager()
        status_queue = manager.Queue()
        
        # Iniciar proceso de descarga
        proc = multiprocessing.Process(
            target=self._download_sync, 
            args=(url, status_queue)
        )
        proc.start()
        
        # Monitorear el progreso
        result = {'status': 'preparing', 'filename': None, 'msg': None}
        loop = asyncio.get_running_loop()
        
        async def monitor_progress():
            nonlocal result
            while True:
                try:
                    status = await loop.run_in_executor(None, status_queue.get, True, 1)
                    if status is None:
                        break
                    
                    # Actualizar resultado
                    result.update(status)
                    
                    # Calcular porcentaje si es posible
                    if 'downloaded_bytes' in status:
                        total = status.get('total_bytes') or status.get('total_bytes_estimate')
                        if total:
                            result['percent'] = (status['downloaded_bytes'] / total) * 100
                    
                    # Llamar callback si se proporcionó
                    if callback:
                        await callback(result.copy())
                        
                    # Si terminó, salir del bucle
                    if status.get('status') in ['finished', 'error']:
                        break
                        
                except:
                    # Timeout o error, continuar
                    continue
        
        # Ejecutar monitoreo y esperar a que termine el proceso
        monitor_task = asyncio.create_task(monitor_progress())
        await loop.run_in_executor(None, proc.join)
        
        # Asegurar que el monitoreo termine
        status_queue.put(None)
        await monitor_task
        
        proc.close()
        
        log.info(f"MP3 download completed for {url}: {result['status']}")
        return result


# Función standalone para exportar
async def download_video_as_mp3(url, download_dir, output_template="%(title)s.%(ext)s", progress_callback=None):
    """
    Función standalone para descargar un video como MP3 en la mejor calidad
    
    Args:
        url (str): URL del video a descargar
        download_dir (str): Directorio donde guardar el archivo
        output_template (str): Plantilla para el nombre del archivo
        progress_callback (callable, optional): Función para recibir actualizaciones de progreso
    
    Returns:
        dict: Resultado de la descarga
    
    Ejemplo de uso:
        result = await download_video_as_mp3(
            "https://www.youtube.com/watch?v=VIDEO_ID",
            "/path/to/downloads",
            progress_callback=lambda status: print(f"Progreso: {status}")
        )
    """
    downloader = SimpleDownloader(download_dir, output_template=output_template)
    return await downloader.download_mp3(url, progress_callback)