import time
from urllib.request import urlopen

import numpy as np
import rasterio
from rasterio import MemoryFile

from core_components.config import get_config
from core_components.logger import setup_logger

logger = setup_logger(__name__)
cfg = get_config()

HOYDEDATA_LAYER = cfg["hoydedata"]["hoydedata_layer"]
HOYDEDATA_URL = cfg["hoydedata"]["hoydedata_url"]
CRS = cfg["global"]["crs_default"]  # default crs


def check_api_status():
    """
    Check if the høydedata API is up and running
    Args:
    Returns:
        bool: True if the API is up and running, False otherwise
    """
    xmin, ymin, xmax, ymax, width, height, nodata = 261906, 6650936, 264220, 6651626, 462, 138, -9999
    request_url = HOYDEDATA_URL.format(HOYDEDATA_LAYER, xmin, ymin, xmax, ymax, width, height, nodata)


    attempts = 0
    wait_time = 1
    while attempts < 10:
        try:
            _ = urlopen(request_url).read()
            break
        except Exception:
            attempts += 1
            time.sleep(wait_time)
    else:
        return False
    return True


def request_hoydedata(bounds:tuple, res:int=5, nodata:int=-9999, max_retries:int=5) -> bytes:
    """
    Get the digital elevation model from the given bounds from the høydedata API

    Args:
        bounds: tuple with the bounding box (xmin, ymin, xmax, ymax)
        res: resolution of the raster
        nodata: nodata value
        max_retries: maximum number of retries

    Returns:
        tif_bytes: bytes of the tif file
    """
    xmin, ymin, xmax, ymax = bounds
    xmin -= 10
    xmax += 10
    ymin -= 10
    ymax += 10

    width = int((xmax - xmin) / res)
    height = int((ymax - ymin) / res)


    request_url = HOYDEDATA_URL.format(HOYDEDATA_LAYER, xmin, ymin, xmax, ymax, width, height, nodata)

    attempts = 0
    wait_time = 1
    while attempts < max_retries:
        try:
            tif_bytes = urlopen(request_url).read()
            break
        except Exception:
            attempts += 1
            time.sleep(wait_time)
    else:
        print(request_url)
        raise Exception("Error (Probably area requested is too big/small or høydedata is down)")
    return tif_bytes


def generate_raster_from_hoydedata(tif_bytes:bytes) -> tuple:
    """
    Generate a raster from the given tif bytes

    Args:
        tif_bytes: bytes of the tif file

    Returns:
        dem_array: numpy array with the elevation values
        dataset_profile: profile of the raster
    """
    try:
        with MemoryFile(tif_bytes) as memfile:
            with memfile.open() as dataset:
                dem_array = dataset.read(1)
                dataset_profile = dataset.profile

    except rasterio.errors.RasterioIOError as e:
        raise(e)
    
    return dem_array, dataset_profile


def get_z_from_hoydedata(point_array: np.ndarray, res=5) -> np.ndarray:
    """
    Set elevation value to the given x,y points
    Args:
        points_xy: numpy array with the x,y coordinates to the points
        window_data: DEM-results from calling get_hoydedata function

    Returns: numpy array with x,y,z coordinates

    """
    if point_array.shape == (2,):
        points_xy = np.expand_dims(point_array,0)
    else:
        points_xy = point_array.copy()
    xmin, ymin = points_xy.min(axis=0)
    xmax, ymax = points_xy.max(axis=0)

    
    tif_bytes = request_hoydedata((xmin,ymin,xmax,ymax), res=res)
    dem_array, profile = generate_raster_from_hoydedata(tif_bytes)
    transform = profile["transform"]

    index = np.array([rasterio.transform.rowcol(transform, xx[0], xx[1]) for xx in points_xy])
    z = np.array([dem_array[xx[0], xx[1]] for xx in index])

    return z
