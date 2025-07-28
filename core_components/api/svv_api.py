import requests
from retry import retry
from shapely import Point
from urllib3.exceptions import MaxRetryError

from core_components.config import get_config
from core_components.logger import setup_logger

logger = setup_logger(__name__)
cfg = get_config()

URL = cfg["svv"]["url"]
CRS = cfg["global"]["crs_default"]
CRS_MAP = cfg["global"]["crs_map"]
LAYER = cfg["svv"]["layer"]


def check_api_status() -> bool:
    """
    Check if the buildings API is up and running
    Args:
    Returns:
        bool: True if the API is up and running, False otherwise
    """
    try:
        response = requests.get(URL, timeout=5,
                                params={"service":"WFS", 
                                        "request": "GetCapabilities"})
    
    except (requests.exceptions.ReadTimeout, MaxRetryError, requests.exceptions.ConnectionError, requests.exceptions.SSLError):
        return False
    except Exception as e:
        logger.error(f"New error when checking api status: {e}")
        return False
    return response.status_code == 200


@retry(tries=3, delay=2, backoff=2)
def get_reports_bbox(bbox):
    params = {
        "service": "WFS",
        "version": "2.0.0", 
        "request": "GetFeature",
        "typeName": "Geoteknikk",
        "outputFormat": "application/json",
        "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:25833"
    }

    response = requests.get(URL, params=params)
    return response.json() if response.status_code == 200 else None


@retry(tries=3, delay=2, backoff=2)
def get_reports_buffer(x,y, buffer=500):
    point = Point(x, y)
    bbox = point.buffer(buffer).bounds
    params = {
        "service": "WFS",
        "version": "2.0.0", 
        "request": "GetFeature",
        "typeName": "Geoteknikk",
        "outputFormat": "application/json",
        "bbox": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:25833"
    }

    response = requests.get(URL, params=params)
    return response.json() if response.status_code == 200 else None

def format_reports(content):
    """
    Format the reports content to a more readable format
    Args:
        content: JSON content from the SVV API
    Returns:
        list: List of formatted report dictionaries
    """
    formatted_reports = []
    for item in content["features"]:
        date_str = item['properties']['DATO']
        formatted_date = f"{date_str[6:8]}-{date_str[4:6]}-{date_str[:4]}"
        formatted_reports.append({
            'id': item['properties']['DOKUMENT_ID'],
            'name': item['properties']['OPPDRAGSNAVN'],
            'date': formatted_date,
            'url': item['properties']['URL']
        })
    return formatted_reports