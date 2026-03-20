import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, List, Optional

from downloader.models import ConversionItem, DownloadStatus, OutputFormat

AUDIO_EXTS = {'.mp3', '.m4a', '.wav', '.ogg', '.flac', '.aac', '.opus'}


class ConvertService:
    def __init__(self, ffmpeg_path: Optional[str] = None):
        if ffmpeg_path is not None:
            self._ffmpeg = ffmpeg_path
        else:
            self._ffmpeg = shutil.which("ffmpeg")  # None if not on PATH

    def convert_all(
        self,
        items: List[ConversionItem],
        out_dir: str,
        output_format: OutputFormat,
        callback: Callable[[ConversionItem], None],
    ) -> None:
        """Start converting all items in a background thread."""
        thread = threading.Thread(
            target=self._run,
            args=(items, out_dir, output_format, callback),
            daemon=True,
        )
        thread.start()

    def _run(
        self,
        items: List[ConversionItem],
        out_dir: str,
        output_format: OutputFormat,
        callback: Callable[[ConversionItem], None],
    ) -> None:
        if not self._ffmpeg:
            for item in items:
                item.status = DownloadStatus.FAILED
                item.error_message = "ffmpeg não encontrado no sistema"
                callback(item)
            return

        for item in items:
            if item.status == DownloadStatus.FAILED:
                callback(item)
                continue

            item.status = DownloadStatus.IN_PROGRESS
            callback(item)

            try:
                input_path = Path(item.input_path)
                stem = input_path.stem
                out_path = Path(out_dir) / f"{stem}.{output_format.value}"

                # Avoid clobbering the source file
                if out_path.resolve() == input_path.resolve():
                    out_path = Path(out_dir) / f"{stem}_converted.{output_format.value}"

                cmd = self._build_cmd(str(input_path), str(out_path), output_format)
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                if result.returncode != 0:
                    raise RuntimeError(result.stderr.decode(errors="replace").strip())

                item.status = DownloadStatus.DONE
            except Exception as exc:
                item.status = DownloadStatus.FAILED
                item.error_message = str(exc)

            callback(item)

    def _build_cmd(
        self,
        input_path: str,
        output_path: str,
        output_format: OutputFormat,
    ) -> List[str]:
        ff = self._ffmpeg
        is_audio_input = Path(input_path).suffix.lower() in AUDIO_EXTS

        if output_format == OutputFormat.MP3:
            return [ff, "-y", "-i", input_path,
                    "-vn", "-c:a", "libmp3lame", "-b:a", "192k",
                    output_path]

        if output_format == OutputFormat.M4A:
            return [ff, "-y", "-i", input_path,
                    "-vn", "-c:a", "aac", "-b:a", "192k",
                    output_path]

        if output_format == OutputFormat.WAV:
            return [ff, "-y", "-i", input_path,
                    "-vn", "-c:a", "pcm_s16le",
                    output_path]

        if output_format == OutputFormat.OGG:
            return [ff, "-y", "-i", input_path,
                    "-vn", "-c:a", "libvorbis", "-q:a", "5",
                    output_path]

        if output_format == OutputFormat.MP4:
            if is_audio_input:
                # Audio → MP4 with black screen video track
                return [ff, "-y",
                        "-f", "lavfi",
                        "-i", "color=black:size=1280x720:rate=1",
                        "-i", input_path,
                        "-c:v", "libx264", "-tune", "stillimage",
                        "-c:a", "aac", "-b:a", "192k",
                        "-pix_fmt", "yuv420p", "-shortest",
                        output_path]
            else:
                return [ff, "-y", "-i", input_path,
                        "-c:v", "libx264", "-c:a", "aac",
                        output_path]

        raise ValueError(f"Unsupported output format: {output_format}")
