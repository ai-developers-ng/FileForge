import requests


class TikaClient:
    def __init__(self, base_url, timeout=60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def extract_text(self, file_path):
        with open(file_path, "rb") as file_handle:
            response = requests.put(
                f"{self.base_url}/tika",
                data=file_handle,
                headers={"Accept": "text/plain"},
                timeout=self.timeout,
            )
        response.raise_for_status()
        return response.text.strip()

    def extract_metadata(self, file_path):
        with open(file_path, "rb") as file_handle:
            response = requests.put(
                f"{self.base_url}/meta",
                data=file_handle,
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        response.raise_for_status()
        return response.json()
