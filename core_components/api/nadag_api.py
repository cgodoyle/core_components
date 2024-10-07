import numpy as np
import requests
import asyncio
import httpx

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from core_components.config import get_config
from core_components.logger import setup_logger


logger = setup_logger(__name__)
cfg = get_config()

base_url = cfg["nadag"]["url"]
URL = base_url + '/{collection}/items?f=json'
CRS = cfg["global"]["crs_default"]
CRS_API = cfg["global"]["crs_map"]
COLUMN_MAPPER_BH = cfg["nadag"]["column_mapper_borehole"]
COLUMN_MAPPER_SA = cfg["nadag"]["column_mapper_samples"]
SAMPLE_COLUMNS = cfg["nadag"]["columns_samples"]

collections = requests.get(base_url).json()
valid_crs = {int(xx.split("/")[-1]):xx for xx in collections["crs"] if xx.split("/")[-1].isnumeric()}
valid_collections = [xx["id"] for xx in collections["collections"]]


def get_href(href):
    response = requests.get(href)
    response.raise_for_status()
    data = response.json()

    if all([xx in data.keys() for xx in ('numberReturned', 'numberMatched')]):
        if data["numberReturned"] < data["numberMatched"]:
            response = requests.get(href, params={'limit': data["numberMatched"]+1})
            response.raise_for_status()
            data = response.json()

    return data


async def get_async(href: str) -> dict:
    if href is None:
        return None
    timeout = httpx.Timeout(120)
    async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(href) 
            data = response.json()

            if all([xx in data.keys() for xx in ('numberReturned', 'numberMatched')]):
                if data["numberReturned"] < data["numberMatched"]:
                    response = await client.get(href, params={'limit': data["numberMatched"]+1}) 
                    data = response.json()

    return data


async def get_href_list(href_list):
    return await asyncio.gather(*[get_async(href) for href in href_list])


async def get_soundings(soudings_href_list, method):
    
    sounding_type_dict = {"rp": "statiskSondering", 
                          "tot": "kombinasjonSondering", 
                          "cpt": "trykksondering", 
                          "prv": "geotekniskProveserie"}
    
    assert method in sounding_type_dict.keys(), f"soundings_type must be one of {sounding_type_dict.keys()}"

    
    soundings_type = sounding_type_dict[method]

    ksd_list = await get_href_list(soudings_href_list)
    ksd_href_list = [xx["properties"][f"{soundings_type}Observasjon"]["href"] if xx is not None else None for xx in ksd_list]
    ks_data = await get_href_list(ksd_href_list)

    ks_data_df = []
    for ii, item in enumerate(ks_data):
        if item is None: 
            new_elem = pd.DataFrame(columns=COLUMN_MAPPER_BH.values())            
        else:
            features = item["features"]
            properties = [ii["properties"] for ii in features]
            data = pd.DataFrame.from_dict(properties)
            if len(data) == 0:
                new_elem = pd.DataFrame(columns=COLUMN_MAPPER_BH.values())
            else:
                if method == "cpt":
                    data["alpha"] = ksd_list[ii]["properties"]["alpha"]
                
                try:
                    if "observasjonKode" not in data.columns:
                        data["observasjonKode"] = None
                    data["observasjonKode"] = data.observasjonKode.replace(np.nan, None)
                    data.columns = data.columns.str.lower()

                    new_elem = (
                        data.rename(columns=COLUMN_MAPPER_BH)
                            .sort_values(by="depth")
                            .reset_index(drop=True)
                                )
                except Exception as e:
                    print(e)
                    print(method)
                    print(data.columns)
                    print(len(data))
                
                if method == 'tot':
                    new_elem[["hammering", "increased_rotation_rate", "flushing"]] = create_intervals_from_comments(new_elem)
                else:
                    new_elem[["hammering", "increased_rotation_rate", "flushing"]] = False


        ks_data_df.append(new_elem)
    
    return ks_data_df


async def get_all_soundings(borehullunders: gpd.GeoDataFrame):
    gbhu = borehullunders.copy()
    gbhu = gbhu.rename(columns={"metode-StatiskSondering": "ss",
                                "metode-KombinasjonSondering": "ks",
                                "metode-Trykksondering": "ts",
                                "metode-GeotekniskPrøveserie": "ps",})
    for xx in ["ss", "ks", "ts", "ps"]:
        if xx not in gbhu.columns:
            gbhu[xx] = None

    gbhu["lokalId"] = gbhu.identifikasjon.map(lambda x: x["lokalId"])

    ss_href_list = {xx.lokalId: xx.ss[0]["href"] if isinstance(xx.ss, list) else None for xx in gbhu.dropna(subset=["ss"]).itertuples()}
    ks_href_list = {xx.lokalId: xx.ks[0]["href"] if isinstance(xx.ks, list) else None for xx in gbhu.dropna(subset=["ks"]).itertuples()}
    ts_href_list = {xx.lokalId: xx.ts[0]["href"] if isinstance(xx.ts, list) else None for xx in gbhu.dropna(subset=["ts"]).itertuples()}
    # ps_href_list = {xx.identifikasjon['lokalId']: xx.ps[0]["href"] if isinstance(xx.ps, list) else None for xx in gbhu.dropna(subset=["ps"]).itertuples()}

    logger.info("fetching rp")
    ss = await get_soundings(list(ss_href_list.values()), method = "rp")
    logger.info("fetching ks")
    ks = await get_soundings(list(ks_href_list.values()), method = "tot")
    logger.info("fetching cpt")
    ts = await get_soundings(list(ts_href_list.values()), method = "cpt")
    # ps = await get_soundings(list(ps_href_list.values()), method = "prv")
    
    borehole_list = []

    logger.info("creating gdf")
    for ref, data, method in zip([ss_href_list, ks_href_list, ts_href_list],[ss, ks, ts], ['rp', 'tot', 'cpt']):
        logger.info(method)
        if len(data) == 0:
            continue
        boreholes = gpd.GeoDataFrame(columns=['method_type', 'geometry', 'location_name', 'data', 'x', 'y', 'z','depth', 
        'method_id', 'method_status', 'method_status_id'], 
        crs=gbhu.crs)

        boreholes['data'] = data
        boreholes['method_type'] = method
        boreholes['method_id'] = list(ref.keys())
        boreholes['depth'] = [xx["depth"].max() for xx in data]
        boreholes[["x", "y"]] = list(map(lambda x: gbhu.query("lokalId == @x").get_coordinates().values.squeeze().tolist(), ref.keys()))
        boreholes['z'] = list(map(lambda x: gbhu.query("lokalId == @x")['høyde'].values.squeeze().tolist(), ref.keys()))
        boreholes["geometry"] = list(map(lambda x: gbhu.query("lokalId == @x").geometry.iloc[0], ref.keys()))
        boreholes["location_name"] = list(map(lambda x: get_href(gbhu.query("lokalId == @x").iloc[0].undersPkt["href"])["properties"]["boreNr"], ref.keys()))
        boreholes["method_status_id"] = 3
        boreholes["method_status"] = "conducted"
        borehole_list.append(boreholes)

    if len(borehole_list) >0:
        boreholes_out = pd.concat(borehole_list)
        boreholes_out = boreholes_out.reset_index(drop=True)
    else:
        boreholes_out = None
    return boreholes_out


def get_collection(collection, bounds):
    
    bbox = gpd.GeoDataFrame(geometry=[box(*bounds)], crs=CRS).to_crs(CRS_API).total_bounds
    url = URL.format(collection=collection)
    params = {
        'bbox': ','.join(map(str, bbox)),
        'crs': valid_crs[CRS],
        'limit': 1
    }
    # print(requests.Request('GET', url, params=params).prepare().url)
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    if data["numberReturned"] < data["numberMatched"]:
        params['limit'] = data["numberMatched"]+1
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    features = data['features']
    if len(features) == 0:
        return gpd.GeoDataFrame()
    return gpd.GeoDataFrame.from_features(features, crs=CRS)


async def get_samples(gbhu):
    gbhu = gbhu.rename(columns={"metode-GeotekniskPrøveserie": "ps"})
    if "ps" not in gbhu.columns:
        return None
    bh = gbhu.dropna(subset=["ps"]).copy()
    bh["lokalId"] = bh.identifikasjon.map(lambda x: x["lokalId"])
    
    href_list = list(map(lambda x: x["href"], bh.ps.map(lambda x: x[0])))
    samples = await get_href_list(href_list)

    href_list = list(map(lambda x: x["href"], bh.undersPkt))
    borenr = await get_href_list(href_list)
    bh["borenr"] = [xx["properties"]["boreNr"] for xx in borenr]
    
    sample_info = [feature["properties"] for p in samples for feature in p["features"]]
    sample_df = pd.DataFrame(sample_info)
    sample_df["lokalId"] = sample_df.identifikasjon.map(lambda x: x["lokalId"])
    sample_df = sample_df.drop(columns=["identifikasjon"])    
    
    href_list = sample_df.harPrøveseriedel.map(lambda x: x["href"]).to_list()
    samples_psd = await get_href_list(href_list)
    
    sample_data_general_dict = [feature["properties"] for p in samples_psd for feature in p["features"]]
    sample_data_general = pd.DataFrame(sample_data_general_dict)
    sample_data_general["ps_id"] = sample_data_general["tilhørerPrøveserie"].map(lambda x: x["title"])
    sample_data_general = sample_data_general.drop(columns=["tilhørerPrøveserie"])


    href_list = [p["harData"]["href"] if "harData" in p else None for p in sample_data_general_dict ]
    sample_data_dict = await get_href_list(href_list)
    
    sample_data = pd.DataFrame([feature["properties"] for p in sample_data_dict for feature in p["features"]])

    sample_data["psd_id"] = sample_data["tilhørerPrøveseriedel"].map(lambda x: x["title"])
    sample_data = sample_data.drop(columns=["tilhørerPrøveseriedel"])
    

    sample_merged = (
        sample_data.merge(sample_data_general, left_on="psd_id", right_on="prøveseriedelId", suffixes=('', '_general'))
                   .merge(sample_df[["lokalId", "geotekniskborehullunders"]], left_on="ps_id", right_on="lokalId", suffixes=('', '_df'))
                   .merge(bh, left_on="geotekniskborehullunders", right_on="lokalId", suffixes=('', '_bh'))
                     )
    
    for col in SAMPLE_COLUMNS:
        if col not in sample_merged.columns:
            sample_merged[col] = None

    sample_merged = sample_merged[SAMPLE_COLUMNS]
    columns_to_drop = [col for col in sample_merged.columns if col.endswith('_general') or col.endswith('_df') or col.endswith('_bh')]
    sample_merged = sample_merged.drop(columns=columns_to_drop)

    sample_merged.columns = sample_merged.columns.str.lower()

    sample_merged = sample_merged.rename(columns=COLUMN_MAPPER_SA)
    sample_merged['layer_composition'] = sample_merged['layer_composition'].map(lambda x: str(x).lower())
    
    samples_gdf = gpd.GeoDataFrame(sample_merged, crs=bh.crs) if len(sample_merged) > 0 else None

    if samples_gdf is not None:
        # field manager placeholders
        samples_gdf["method_status_id"] = 3
        samples_gdf["method_type"] = "sa"
        samples_gdf["method_status"] = "conducted"
        samples_gdf["method_id"] = 4

        samples_gdf[['x', 'y']] = samples_gdf.get_coordinates().round(1)
        samples_gdf["z"] = samples_gdf["location_elevation"]
        samples_gdf["depth"] = (samples_gdf.depth_base + samples_gdf.depth_top)/2

    return samples_gdf


def get_rock_depth_dataset(bounds: tuple) -> gpd.GeoDataFrame:
    """
    Get rock depth dataset from NADAG

    Args:
        bounds (tuple): (minx, miny, maxx, maxy)

    Returns:
        gpd.GeoDataFrame: Rock depth dataset
    """
    gbhu = get_collection("geotekniskborehullunders", tuple(bounds))
    gdf = gbhu[["boretLengdeTilBerg", "høyde", "geometry"]].dropna(subset="boretLengdeTilBerg")
    gdf["rock_depth"] = gdf.boretLengdeTilBerg.map(lambda x: x.get('borlengdeTilBerg'))
    gdf = gdf.drop(columns="boretLengdeTilBerg")
    gdf = gdf.rename(columns={"høyde": "elevation"})
    gdf["rock_elevation"] = gdf.elevation - gdf.rock_depth
    return gdf[["geometry", "elevation", "rock_depth", "rock_elevation"]]


def create_flagged_column(df, col_start, col_end):
    changes = pd.Series(0, index=df.index)
    changes[df[col_start]] = 1
    changes[df[col_end]] = -1
    
    cum_state = changes.cumsum()
    
    return cum_state > 0


def create_intervals_from_comments(input_df):
    df = input_df.copy()
    flag_codes = cfg["nadag"]["flag_codes"]


    df["comment_code"] = df["comment_code"].map(lambda x: str(int(x)) if x is not None and not isinstance(x, str) else x)
    for col, codes in flag_codes.items():
        df[col] = df["comment_code"].apply(lambda x: any(code in x for code in codes) if x is not None else False)

    for col in ["hammering", "increased_rotation_rate", "flushing"]:
           df[col] = create_flagged_column(df, col+"_starts", col+"_ends")
    
    return df[["hammering", "increased_rotation_rate", "flushing"]]