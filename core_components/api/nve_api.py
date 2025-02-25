import requests
import io
from urllib3.exceptions import MaxRetryError

import geopandas as gpd
from shapely.geometry import box

from core_components.logger import setup_logger
from core_components.config import get_config

logger = setup_logger(__name__)
cfg = get_config()


def get_faresoner(bounds:tuple) -> gpd.GeoDataFrame:
    """

    """
    url = "https://wfs.geonorge.no/skwms1/wfs.kvikkleire?service=wfs"
    gdf = gpd.GeoDataFrame([1], geometry=[box(*bounds)], crs=25833)
    gdf = gdf.to_crs(4326)

    bbox_reprojected = gdf.total_bounds
    xmin, ymin, xmax, ymax = bbox_reprojected 
    
    params = {
        "request": "GetFeature",
        "service": "WFS",
        "version": "2.0.0",
        "typename": "UtlosningOmr",
        "srsname": "EPSG:25833",
        "bbox": f"{ymin},{xmin},{ymax},{xmax}"
    }
    response = requests.get(url, params=params)
    response.raise_for_status
    dataset = gpd.GeoDataFrame(geometry=[], crs=25833)

    if response.status_code == 200:
        content = response.content
    else:
        return dataset

    try:
        file_like_object = io.BytesIO(content)
        dataset = gpd.read_file(file_like_object)

    except Exception as e:
        # print(e)
        # print(response.url)
        return dataset

    return dataset


def get_omr_uten_fare(bounds):
    dataset = get_faresoner(bounds)
    dataset = dataset.query("skredFaregradKlasse == 'Ingen'")
    return dataset


