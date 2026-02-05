import os


def ensure_dirs(*paths):
    for path in paths:
        os.makedirs(path, exist_ok=True)


def result_paths(result_dir, job_id):
    json_path = os.path.join(result_dir, f"{job_id}.json")
    text_path = os.path.join(result_dir, f"{job_id}.txt")
    pdf_path = os.path.join(result_dir, f"{job_id}.pdf")
    return json_path, text_path, pdf_path


def image_result_path(result_dir, job_id, output_format):
    """Generate path for converted image output."""
    return os.path.join(result_dir, f"{job_id}.{output_format}")


def document_result_path(result_dir, job_id, output_format):
    """Generate path for converted document output."""
    return os.path.join(result_dir, f"{job_id}_doc.{output_format}")


def audio_result_path(result_dir, job_id, output_format):
    """Generate path for converted audio output."""
    return os.path.join(result_dir, f"{job_id}_audio.{output_format}")


def video_result_path(result_dir, job_id, output_format):
    """Generate path for converted video output."""
    return os.path.join(result_dir, f"{job_id}_video.{output_format}")
