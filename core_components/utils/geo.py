import geopandas as gpd
from shapely.geometry import box

def split_bbox(bbox:gpd.GeoDataFrame, n_rows:int, n_cols:int) -> list[gpd.GeoDataFrame]:
    """
    
    """
    minx, miny, maxx, maxy = bbox.total_bounds
    width = (maxx - minx) / n_cols
    height = (maxy - miny) / n_rows
    sub_boxes = []
    for i in range(n_cols):
        for j in range(n_rows):
            sub_minx = minx + i * width
            sub_miny = miny + j * height
            sub_maxx = sub_minx + width
            sub_maxy = sub_miny + height
            sub_boxes.append(box(sub_minx, sub_miny, sub_maxx, sub_maxy))
    subgrid = gpd.GeoDataFrame(geometry=sub_boxes, crs = bbox.crs)
    subgrid["id"] = range(len(subgrid))
    return subgrid