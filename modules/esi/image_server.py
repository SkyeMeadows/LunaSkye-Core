import requests
import base64
from io import BytesIO
from modules.utils.logging_setup import get_logger

log = get_logger("testing_images")

async def get_image(id):
    headers = {
                "Content-Type": "application/json",
                "User-Agent": "LunaSkye Core (admin contact: skyemeadows20@gmail.com)",
            }
    
    log.debug(f"setting url with headers")
    url = f"https://images.evetech.net/types/{id}/icon"
    log.debug(f"URL set to {url}")

    log.debug(f"attempting ESI request with url and headers, timeout 10s")
    response = requests.get(url, headers=headers, timeout=10)
    log.debug(f"Response code is: {response.status_code}")

    image_content = response.content
    image_base64 = base64.b64encode(image_content).decode('utf-8')
    data_url = f"data:image/png;base64,{image_base64}"

    log.debug(f"Attemtping to return image")
    return data_url