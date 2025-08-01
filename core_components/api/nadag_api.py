import asyncio

import geopandas as gpd
import httpx
import numpy as np
import pandas as pd
import requests
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
TIMEOUT = cfg["nadag"]["timeout"]
QCL_KWD = ["quick", "kvikk", "sprøbrudd"]

# collections = requests.get(base_url).json()
# valid_crs = {int(xx.split("/")[-1]):xx for xx in collections["crs"] if xx.split("/")[-1].isnumeric()}
# valid_collections = [xx["id"] for xx in collections["collections"]]


def check_api_status():
    try:
        response = requests.get(base_url, timeout=5)
    except requests.exceptions.ReadTimeout:
        return False
    except Exception as e:
        logger.error(f"New error when checking api status: {e}")
        return False
    return response.status_code == 200


def get_api_data():
    if not check_api_status():
        valid_collections = [
            'deformasjonmaling',
            'dynamisksondering',
            'dynamisksonderingdata',
            'geotekniskborehull',
            'geotekniskborehullunders',
            'geotekniskdokument',
            'geotekniskfeltunders',
            'geotekniskproveserie',
            'geotekniskproveseriedel',
            'geotekniskproveseriedeldata',
            'geoteknisktolketlag',
            'geoteknisktolketpunkt',
            'geotekniskunders',
            'grunnvanndata',
            'grunnvannmaling',
            'kjerneprove',
            'kombinasjonsondering',
            'kombinasjonsonderingdata',
            'miljoundersokelse',
            'poretrykkdatainsitu',
            'statisksondering',
            'statisksonderingdata',
            'trykksondering',
            'trykksonderingdata',
            'vingeboring',
            'vingeboringdata'
            ]
        valid_crs = {
            25833: 'http://www.opengis.net/def/crs/EPSG/0/25833',
            25832: 'http://www.opengis.net/def/crs/EPSG/0/25832',
            4258: 'http://www.opengis.net/def/crs/EPSG/0/4258',
            3857: 'http://www.opengis.net/def/crs/EPSG/0/3857',
            4326: 'http://www.opengis.net/def/crs/EPSG/0/4326'}
    else:
        collections = requests.get(base_url).json()
        valid_crs = {int(xx.split("/")[-1]):xx for xx in collections["crs"] if xx.split("/")[-1].isnumeric()}
        valid_collections = [xx["id"] for xx in collections["collections"]]
    return valid_collections, valid_crs

valid_collections, valid_crs = get_api_data()

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
    timeout = httpx.Timeout(TIMEOUT)
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


def get_method_id(data):
    if isinstance(data, (gpd.GeoDataFrame, pd.DataFrame)) and not data.empty:
        return data["method_id"].unique()[0]
    else:
        return None


async def get_all_soundings(borehullunders: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Fetches and processes sounding data for given borehole investigations.
    Args:
        borehullunders (gpd.GeoDataFrame): A GeoDataFrame containing borehole investigation data.
    Returns:
        gpd.GeoDataFrame or None: A GeoDataFrame containing processed borehole sounding data, or None if no data is available.
    """
    if borehullunders.empty:
        return None
    
    gbhu = borehullunders.copy()
    gbhu = gbhu.rename(columns={"metode-StatiskSondering": "ss",
                                "metode-KombinasjonSondering": "ks",
                                "metode-Trykksondering": "ts",
                                "metode-GeotekniskPrøveserie": "ps",})
    for xx in ["ss", "ks", "ts", "ps"]:
        if xx not in gbhu.columns:
            gbhu[xx] = None

    gbhu["lokalId"] = gbhu.identifikasjon.map(lambda x: x["lokalId"])

    method_to_location_dict = gbhu.set_index('lokalId')['underspkt_fk'].to_dict()

    ss_href_list = {xx.lokalId: xx.ss[0]["href"] if isinstance(xx.ss, list) else None for xx in gbhu.dropna(subset=["ss"]).itertuples()}
    ks_href_list = {xx.lokalId: xx.ks[0]["href"] if isinstance(xx.ks, list) else None for xx in gbhu.dropna(subset=["ks"]).itertuples()}
    ts_href_list = {xx.lokalId: xx.ts[0]["href"] if isinstance(xx.ts, list) else None for xx in gbhu.dropna(subset=["ts"]).itertuples()}
    # ps_href_list = {xx.identifikasjon['lokalId']: xx.ps[0]["href"] if isinstance(xx.ps, list) else None for xx in gbhu.dropna(subset=["ps"]).itertuples()}

    # ss = await get_soundings(list(ss_href_list.values()), method = "rp")
    # ks = await get_soundings(list(ks_href_list.values()), method = "tot")
    # ts = await get_soundings(list(ts_href_list.values()), method = "cpt")
    # ps = await get_soundings(list(ps_href_list.values()), method = "prv")
    
    ss, ks, ts = await asyncio.gather(
        get_soundings(list(ss_href_list.values()), method = "rp"),
        get_soundings(list(ks_href_list.values()), method = "tot"),
        get_soundings(list(ts_href_list.values()), method = "cpt")
    )

    borehole_list = []


    for ref, data, method in zip([ss_href_list, ks_href_list, ts_href_list],[ss, ks, ts], ['rp', 'tot', 'cpt']):
        if len(data) == 0:
            continue
        boreholes = gpd.GeoDataFrame(columns=['method_type', 'geometry', 'location_name', 'data', 'x', 'y', 'z','depth', 
        'method_id', 'method_status', 'method_status_id', 'location_id'], 
        crs=gbhu.crs)

        gbhu_id = list(ref.keys())  # lokalId from geotekniskborehullunders
        methods_id = list(map(get_method_id, data)) # lokalId from the method 

        boreholes['data'] = data
        boreholes['method_type'] = method
        boreholes['gbhu_id'] = gbhu_id
        boreholes['method_id'] = methods_id
        boreholes['depth'] = [xx["depth"].max() for xx in data]
        boreholes["method_status_id"] = 3
        boreholes["method_status"] = "conducted"
       
        borehole_list.append(boreholes)

    if len(borehole_list) > 0:
        boreholes_out = pd.concat(borehole_list)
        boreholes_out = boreholes_out.reset_index(drop=True)
        
        boreholes_out = _get_depth_rock_boreholes(boreholes_out, gbhu)
        boreholes_out["geometry"] = boreholes_out.gbhu_id.map(lambda x: gbhu.query("lokalId == @x").iloc[0]["geometry"])
        boreholes_out[["x", "y"]] = boreholes_out["geometry"].get_coordinates()
        boreholes_out['z'] = boreholes_out.gbhu_id.map(lambda x: gbhu.query("lokalId == @x").iloc[0]["høyde"])
        
        boreholes_out["location_id"] = boreholes_out.gbhu_id.map(method_to_location_dict)
        
        
        upunkt_href = await get_href_list(boreholes_out.gbhu_id.map(lambda x: gbhu.query("lokalId == @x").iloc[0].undersPkt["href"]).to_list())
        boreholes_out["location_name"] = [vv["properties"]["boreNr"] for vv in upunkt_href]

    else:
        boreholes_out = None
    
    geotekniskborehull_list = await get_href_list(boreholes_out.apply(lambda x: get_sounding_urls(x)["location"], axis=1).to_list())
    boreholes_out["geotekniskunders_id"] = list(map(lambda x: x["properties"]["opprinneligGeotekniskUndersID"], geotekniskborehull_list))

    return boreholes_out


def _get_depth_rock_boreholes(boreholes_df, gbhu_df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boreholes = boreholes_df.copy()
    if "boretLengdeTilBerg" not in gbhu_df.columns:
        boreholes["depth_rock"] = np.nan
        boreholes["depth_rock_quality"] = np.nan
    else:
        for item in boreholes.itertuples():
            gbhu_id = item.gbhu_id  # noqa: F841
            gg = gbhu_df.query("lokalId == @gbhu_id").iloc[0]
            if isinstance(gg.boretLengdeTilBerg, dict):
                depth_rock_value = gg.boretLengdeTilBerg.get("borlengdeTilBerg")
                depth_rock_quality_value = gg.boretLengdeTilBerg.get("borlengdeKvalitet")

                boreholes.loc[item.Index, "depth_rock"] = float(depth_rock_value) if depth_rock_value is not None else np.nan
                boreholes.loc[item.Index, "depth_rock_quality"]  = int(depth_rock_quality_value) if depth_rock_quality_value is not None else np.nan
            else:
                boreholes.loc[item.Index, "depth_rock"] = np.nan
                boreholes.loc[item.Index, "depth_rock_quality"] = np.nan
    return boreholes


def get_collection(collection, bounds, limit = 1000):
    """
    Fetches a collection of geospatial data within specified bounds from the NADAG API.
    see documentation at https://ogcapitest.ngu.no/rest/services/grunnundersokelser_utvidet
    Args:
        collection (str): The name of the collection to fetch. For example, 'geotekniskborehullunders'.
        bounds (tuple): A tuple representing the bounding box coordinates (minx, miny, maxx, maxy).
        limit (int, optional): The maximum number of records to fetch per request. Defaults to 1000.
    Returns:
        gpd.GeoDataFrame: A GeoDataFrame containing the fetched geospatial data. Returns an empty GeoDataFrame if no data is found.
    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
        ValueError: If the response cannot be parsed as JSON.
    """
    
    bbox = gpd.GeoDataFrame(geometry=[box(*bounds)], crs=CRS).to_crs(CRS_API).total_bounds
    url = URL.format(collection=collection)

    ss = f"{bbox[0]} {bbox[1]},{bbox[0]} {bbox[3]},{bbox[2]} {bbox[3]},{bbox[2]} {bbox[1]},{bbox[0]} {bbox[1]}"


    params = {
        'filter-lang': 'cql2-text',
        'filter': f"S_INTERSECTS(posisjon,POLYGON(({ss})))",
        'crs': valid_crs[CRS],
        'limit': limit
    }


    data_list = []
    next_page = True
    cont = 0

    while next_page:
        cont += 1
        response = requests.get(url, params if cont == 1 else None)
        # print(response.url)
        response.raise_for_status()
        try:
            data = response.json()
        except Exception as e:
            print("Error in response")
            print(requests.Request('GET', url).prepare().url)
            raise e


        links_rel = list(map(lambda x: x.get("rel"), data["links"]))
        if "next" in links_rel:
            url = list(filter(lambda x: x.get("rel") == "next", data["links"]))[0]["href"]
            next_page = True
        else:
            next_page = False
        data_list.extend(data["features"])
    if len(data_list) == 0:
        return gpd.GeoDataFrame()
    else:
        return gpd.GeoDataFrame.from_features(data_list, crs=CRS)
    

def get_collection_bbox(collection, bounds, limit = 1000):
    """
    Fetches a collection of geospatial data within specified bounds from the NADAG API.
    see documentation at https://ogcapitest.ngu.no/rest/services/grunnundersokelser_utvidet
    Args:
        collection (str): The name of the collection to fetch. For example, 'geotekniskborehullunders'.
        bounds (tuple): A tuple representing the bounding box coordinates (minx, miny, maxx, maxy).
        limit (int, optional): The maximum number of records to fetch per request. Defaults to 1000.
    Returns:
        gpd.GeoDataFrame: A GeoDataFrame containing the fetched geospatial data. Returns an empty GeoDataFrame if no data is found.
    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
        ValueError: If the response cannot be parsed as JSON.
    """
    
    bbox = gpd.GeoDataFrame(geometry=[box(*bounds)], crs=CRS).to_crs(CRS_API).total_bounds
    url = URL.format(collection=collection)
    params = {
        'bbox': ','.join(map(str, bbox)),
        'crs': valid_crs[CRS],
        'limit': limit
    }
    
    
    data_list = []
    next_page = True
    cont = 0
    while next_page:
        cont += 1
        response = requests.get(url, params=params if cont == 1 else None)
        print(response.url)
        response.raise_for_status()
        try:
            data = response.json()
        except Exception as e:
            print("Error in response")
            print(requests.Request('GET', url).prepare().url)
            raise e
            
        
        links_rel = list(map(lambda x: x.get("rel"), data["links"]))
        if "next" in links_rel:
            url = list(filter(lambda x: x.get("rel") == "next", data["links"]))[0]["href"]
            next_page = True
        else:
            next_page = False
        data_list.extend(data["features"])
    if len(data_list) == 0:
        return gpd.GeoDataFrame()
    else:
        return gpd.GeoDataFrame.from_features(data_list, crs=CRS)


async def get_samples(gbhu, aggregate=True, map_layer_composition=True) -> gpd.GeoDataFrame:
    gbhu = gbhu.rename(columns={"metode-GeotekniskPrøveserie": "ps"})
    if "ps" not in gbhu.columns:
        return None
    bh = gbhu.dropna(subset=["ps"]).copy()
    bh["lokalId"] = bh.identifikasjon.map(lambda x: x["lokalId"])

    method_to_location_dict = bh.set_index('lokalId')['underspkt_fk'].to_dict()
    
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
    
    sample_merged = sample_merged.drop(columns=
                                       ['lagposisjon', 'prøvemetode', 'labanalyse', 'boretlengde', 
                                        'geotekniskproveseriedel', 'observasjonkode', 
                                        'aksieldeformasjon', 'opphav', 'høydereferanse', 
                                        'opprettetdato', 'geotekniskmetode', 'boretazimuth', 'borethelningsgrad', 
                                        'boretlengdetilberg', 'undersøkelsestart','forboretlengde', 'stoppkode', 
                                        'forboretstartlengde'], 
                                        errors="ignore")

    if len(sample_merged) > 0:
        sample_merged["layer_composition_full"] = sample_merged["layer_composition"]
        if aggregate:

            sample_merged = aggregate_samples(sample_merged, id_field='method_id')
        elif map_layer_composition:
            
            sample_merged["layer_composition"] = sample_merged.layer_composition.map(
                _clf_single
                )
        

    samples_gdf = gpd.GeoDataFrame(sample_merged, crs=bh.crs) if len(sample_merged) > 0 else None

    if samples_gdf is not None:
        # field manager placeholders
        samples_gdf["method_status_id"] = 3
        samples_gdf["method_type"] = "sa"
        samples_gdf["method_status"] = "conducted"
        # samples_gdf["method_id"] = 4

        samples_gdf[['x', 'y']] = samples_gdf.get_coordinates().round(1)
        samples_gdf["z"] = samples_gdf["location_elevation"]
        samples_gdf["depth"] = samples_gdf.apply(_get_sample_depth, axis=1)

        
        samples_gdf["location_id"] = samples_gdf.gbhu_id.map(method_to_location_dict)

    
    return samples_gdf


def _get_sample_depth(sample) -> float:
    if (sample.depth_top > sample.depth_base) and (sample.depth_base == 0):
        depth = sample.depth_top
    elif pd.isna(sample.depth_base) and not pd.isna(sample.depth_top):
        depth = sample.depth_top
    elif sample.depth_top == sample.depth_base:
        depth = sample.depth_top
    else:
        try:
            depth = (sample.depth_top + sample.depth_base) / 2
        except TypeError:
            depth = np.nan
    return depth


def _clf_aggr(x):
    values = x.unique()
    if all([vv in ("nan", "none") for vv in values]):
        return "nothing"
    else:
        for xx in values:
            if any(kwd in xx.lower() for kwd in QCL_KWD):
                return "quick_clay"
        return 'other'
        

def _clf_single(x):
    if x in ("nan", "none"):
        return "nothing"
    if any(kwd in x.lower() for kwd in QCL_KWD):
        return "quick_clay"
    else:
        return "other"


def aggregate_samples(samples_gdf: gpd.GeoDataFrame, id_field:str = 'method_id') -> gpd.GeoDataFrame:
    # prøveseriedelid is now used as method_id instead of geotekniskborehullunders_id
    def take_any(x):
        return x.iloc[0]
    
    def join_texts(x):
        # Filter out None, "nan", "none", and empty strings
        filtered_x = [item for item in x if item is not None and str(item).lower() not in ("nan", "none", "") and str(item).strip() != ""]
        # Join with ' | ' if there are any values left, otherwise return "-"
        return ' | '.join(filtered_x) if filtered_x else "-"
    
    default_agg_func = take_any

    agg_funcs = {
        'water_content': 'mean',    # Sumar los valores de la columna A
        'layer_composition': _clf_aggr,
        'layer_composition_full': join_texts,
        'liquid_limit': 'mean', 
        'plastic_limit': 'mean',
        'strength_undisturbed': 'min',
        'strength_undrained': 'min',
        'strength_remoulded': 'min',

    }


    # Crear un diccionario de funciones de agregación que incluya la función por defecto
    agg_funcs_with_default = {col: agg_funcs.get(col, default_agg_func) for col in samples_gdf.columns}
    samples = samples_gdf.groupby(id_field, as_index=False).agg(agg_funcs_with_default)


    return samples


def get_sounding_urls(item: pd.Series) -> dict:
    """
    Get the urls for the different tables in the NADAG API for a given item.
    A sounding can be either a borehole or a sample.
    
    Args:
        item (pd.Series): A Series containing the sounding data (a item/slice in a DataFrame).
    Returns:
        dict: A dictionary containing the urls for the different tables in the NADAG
            API for the given item.

    """
    
    method_id = item.method_id if "method_id" in item.index else None
    location_id = item.location_id if "location_id" in item.index else None
    gbhu_id = item.gbhu_id if "gbhu_id" in item.index else None
    geotekniskunders_id = item.geotekniskunders_id if "geotekniskunders_id" in item.index else None

    method_type = item.method_type
    method_parser = {"tot": "kombinasjonsondering", "rp": "statisksondering", "cpt": "trykksondering", "sa": "geotekniskproveseriedel"}
    method_nadag = method_parser.get(method_type)
    out = dict(
        geotekniskborehullunders = f"{base_url}/geotekniskborehullunders/items/{gbhu_id}" if gbhu_id is not None else "Not available",
        method =  f"{base_url}/{method_nadag}/items/{method_id}" if method_id is not None else "Not available",
        location = f"{base_url}/geotekniskborehull/items/{location_id}" if location_id is not None else "Not available",
        documents = f"{base_url}/geotekniskdokument/items?tilhorergu_fk={geotekniskunders_id}" if geotekniskunders_id is not None else "Not available",
        infopage = f"https://geo.ngu.no/api/faktaark/nadag/visGeotekniskBorehull.php?id={location_id}" if location_id is not None else "Not available",
        
    )
    return out


async def get_data_big_areas(bounds: tuple, max_dist_query:int=2000,
                             include_samples=True) -> gpd.GeoDataFrame:
    from tqdm.notebook import tqdm

    from core_components.utils.geo import split_bbox

    n_cols, n_rows = max((bounds[2]-bounds[0])//max_dist_query,1),max((bounds[3]-bounds[1])//max_dist_query,1)
    sub_boxes = split_bbox(gpd.GeoDataFrame(geometry=[box(*bounds)], crs=CRS), n_rows, n_cols)
    gbhu_list = []

    for item in tqdm(sub_boxes.itertuples(), total=len(sub_boxes)):
        gbhu = get_collection("geotekniskborehullunders", tuple(item.geometry.bounds))
        gbhu_list.append(gbhu)

    gbhu_list = [item for item in gbhu_list if not (item is None or item.empty)]
    gbhu = pd.concat(gbhu_list)

    borehole_list = []
    sample_list = []

    for ii, item in tqdm(enumerate(gbhu_list)):
        if item.empty:
            borehole_list.append(None)
            sample_list.append(None)
        else:
            try:
                boreholes = await get_all_soundings(item)
                if include_samples:
                    samples = await get_samples(item)
                else:
                    samples = None
            except Exception as e:
                logger.error(f"error at {item.location_name}, index {ii}: {e}")
                boreholes = None
                samples = None
            borehole_list.append(boreholes)
            sample_list.append(samples)

    borehole_gdf = pd.concat(borehole_list, ignore_index=True)
    sample_gdf = pd.concat(sample_list, ignore_index=True)

    return gbhu, borehole_gdf, sample_gdf


def get_rock_depth_dataset(gbhu, 
                           rock_depth_quality_threshold=0,
                           max_depth=25) -> gpd.GeoDataFrame:
    """
    Extract rock depth dataset from NADAG borehole investigations.

    Args:
        gbhu (gpd.GeoDataFrame): GeoDataFrame containing borehole investigation data.
        rock_depth_quality_threshold (int): Minimum quality threshold for rock depth data (0 to 2). 
                                            1=antatt, 2=påvist, 0=no rock.
        max_depth (int): Maximum depth to consider for boreholes without rock depth data.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame containing rock depth information.
    """
    assert 0<=rock_depth_quality_threshold<=2, "rock_depth_quality_threshold must be between 0 and 2"
    
    max_rock_depth_filter = 500  # noqa: F841
    
    _fields = ["geometry", "elevation", "rock_depth", "rock_elevation", "rock_depth_quality", "source"]

    gdf = gbhu[["boretLengdeTilBerg", "høyde", "geometry"]].dropna(subset="boretLengdeTilBerg")
    gdf["rock_depth"] = gdf.boretLengdeTilBerg.map(lambda x: x.get('borlengdeTilBerg'))
    gdf["rock_depth_quality"]  = gdf.boretLengdeTilBerg.map(lambda x: int(x.get('borlengdeKvalitet')) if isinstance(x, dict) else 0)
    gdf = gdf.drop(columns="boretLengdeTilBerg")
    gdf = gdf.rename(columns={"høyde": "elevation"})
    gdf["rock_elevation"] = gdf.elevation - gdf.rock_depth
    gdf["source"] = "nadag"
    gdf = gdf[_fields]
    print(f"Found {len(gdf)} boreholes with rock depth")

    gdf_no_rock = gbhu.query("boretLengdeTilBerg.isnull() and boretLengde >=  @max_depth")[["boretLengde", "høyde", "geometry"]].copy()
    gdf_no_rock["rock_depth"] = gdf_no_rock.boretLengde
    gdf_no_rock = gdf_no_rock.rename(columns={"høyde": "elevation"})
    gdf_no_rock["rock_elevation"] = gdf_no_rock.elevation - gdf_no_rock.rock_depth
    gdf_no_rock["rock_depth_quality"] = 0
    gdf_no_rock["source"] = "nadag_no_rock"
    gdf_no_rock = gdf_no_rock[_fields]
    print(f"Found {len(gdf_no_rock)} boreholes with no rock depth and assuming rock depth at bh's maximum depth")
    print("    Warning: This is a rough estimate! Use it only for categorical analysis")

    gdf_depth = pd.concat([gdf, gdf_no_rock])

    
    gdf_depth = gdf_depth.query("rock_depth < @max_rock_depth_filter and rock_depth_quality >= @rock_depth_quality_threshold")
    
    print(f"Total rock depth dataset: {len(gdf_depth)} boreholes after filtering")

    return gdf_depth


def create_flagged_column(df, col_start_bool_series, col_end_bool_series):
    """
    from gemini

    """
    n = len(df)
    if n == 0:
        return pd.Series([False] * n, index=df.index, dtype=bool)

    active_state_col = pd.Series(False, index=df.index, dtype=bool)
    current_is_active = False

    for i in df.index:
        if col_end_bool_series.loc[i]:
            current_is_active = False
        elif col_start_bool_series.loc[i]:
            current_is_active = True
        
        active_state_col.loc[i] = current_is_active
        
    return active_state_col


def create_intervals_from_comments(input_df):
    """
    from gemini
    """
    df = input_df.copy()

    try:
        flag_codes_config = cfg["nadag"]["flag_codes"]
    except NameError:
        print("No configuration file found. Using empty flag_codes_config.")
        flag_codes_config = {} 
        logger.debug("No configuration file found. Using empty flag_codes_config.")
    except KeyError:
        print("No flag_codes found in configuration. Using empty flag_codes_config.")
        flag_codes_config = {}
        logger.debug("No flag_codes found in configuration. Using empty flag_codes_config.")

    interval_types = ["hammering", "increased_rotation_rate", "flushing"]

    if "comment_code" not in df.columns:
        logger.debug("Column 'comment_code' not found in DataFrame. Returning empty DataFrame.")
        default_false_series = pd.Series(False, index=df.index, dtype=bool)
        return pd.DataFrame({col: default_false_series for col in interval_types})


    def format_comment_value(value):
        if pd.isna(value):
            return ""  
        if isinstance(value, (int, float)):
            return str(int(value)) 
        return str(value) 

    df["comment_code_str"] = df["comment_code"].apply(format_comment_value)

   
    for event_col_name, target_codes in flag_codes_config.items():
        if not isinstance(target_codes, list):
            df[event_col_name] = pd.Series(False, index=df.index, dtype=bool)
            logger.debug(f"Column '{event_col_name}' in flag_codes_config is not a list. Setting to False.")
            continue
        
        str_target_codes = [str(tc) for tc in target_codes]
        df[event_col_name] = df["comment_code_str"].apply(
            lambda comment_str: any(target_code in comment_str for target_code in str_target_codes)
        )
    
    for base_col_name in interval_types:
        start_event_col_name = base_col_name + "_starts"
        end_event_col_name = base_col_name + "_ends"
        

        if start_event_col_name not in df.columns:
            df[start_event_col_name] = pd.Series(False, index=df.index, dtype=bool)
        if end_event_col_name not in df.columns:
            df[end_event_col_name] = pd.Series(False, index=df.index, dtype=bool)
            
        df[base_col_name] = create_flagged_column(
            df, 
            df[start_event_col_name], 
            df[end_event_col_name]
        )
    
    return df[interval_types]



def create_flagged_column_old(df, col_start, col_end):
    changes = pd.Series(0, index=df.index)
    changes[df[col_start]] = 1
    changes[df[col_end]] = -1
    
    cum_state = changes.cumsum()
    
    return cum_state > 0


def create_intervals_from_comments_old(input_df):
    df = input_df.copy()
    flag_codes = cfg["nadag"]["flag_codes"]


    df["comment_code"] = df["comment_code"].map(lambda x: str(int(x)) if x is not None and not isinstance(x, str) else x)
    for col, codes in flag_codes.items():
        df[col] = df["comment_code"].apply(lambda x: any(code in x for code in codes) if x is not None else False)

    for col in ["hammering", "increased_rotation_rate", "flushing"]:
           df[col] = create_flagged_column(df, col+"_starts", col+"_ends")
    
    return df[["hammering", "increased_rotation_rate", "flushing"]]