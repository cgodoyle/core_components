import requests
import io

import geopandas as gpd
from shapely.geometry import box

from core_components.logger import setup_logger
from core_components.config import get_config

logger = setup_logger(__name__)
cfg = get_config()

URL = cfg["buildings"]["url"]
COLS = cfg["buildings"]["columns"]
FILTER = cfg["buildings"]["query_filter"]
CRS = cfg["global"]["crs_default"]
CRS_MAP = cfg["global"]["crs_map"]


def check_api_status():
    response = requests.get(URL, params={"service":"WFS", 
                                         "request": "GetCapabilities"})
    if response.status_code == 200:
        return True
    else:
        return False


def get_building_points(bounds):
    
    gdf = gpd.GeoDataFrame([1], geometry=[box(*bounds)], crs=CRS)
    gdf = gdf.to_crs(CRS_MAP)

    bbox_reprojected = gdf.total_bounds
    xmin, ymin, xmax, ymax = bbox_reprojected 
    
    params = {
        "request": "GetFeature",
        "service": "WFS",
        "version": "2.0.0",
        "typename": "app:Bygning",
        "srsname": "EPSG:25833",
        "bbox": f"{ymin},{xmin},{ymax},{xmax}"
    }
    response = requests.get(URL, params=params)
    
    dataset = gpd.GeoDataFrame(geometry=[], crs=CRS)

    if response.status_code == 200:
        content = response.content
    else:
        return dataset
        
    try:
        file_like_object = io.BytesIO(content)
        dataset = gpd.read_file(file_like_object, engine="fiona")
        dataset = _format_dataset(dataset)
    except Exception:
        # print(e)
        return dataset
    
    return dataset


def _format_dataset(dataset):
    out_dataset = dataset.copy()
    out_dataset = out_dataset[COLS].query(FILTER)
    return out_dataset