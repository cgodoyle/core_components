import geopandas as gpd
import requests
import time
from bs4 import BeautifulSoup
import json

from core_components.config import get_config

cfg = get_config()
URL = cfg["consequence"]["url"]


def poly_to_esri(poly:gpd.GeoDataFrame) -> str:
    """
    Convert a geopandas/shapely polygon to an ESRI geometry string
    Args:
        poly: GeoDataFrame with the polygon
    Returns:
        str: ESRI geometry string
    """
    geojson = poly.geometry.iloc[0].__geo_interface__
    esri_geometry = {
        "rings": [geojson['coordinates'][0]],
        "spatialReference": {"wkid": poly.crs.to_epsg()}
    }
    esri_geometry_string = json.dumps(esri_geometry)
    return esri_geometry_string


def check_job_status(job_id:str) -> dict:
    """
    Check the status of a job
    Args:
        job_id: id of the job
    Returns:
        dict: job status
    """
    job_status_url = f"{URL}/jobs/{job_id}"

    status_url = f"{job_status_url}?f=json"
    response = requests.get(status_url)
    if response.status_code == 200:
        job_status = response.json()
        return job_status
    else:
        print(response.status_code)
        return None

def request_consequence_nve(polygon:gpd.GeoDataFrame, items:tuple=("Beboere","Barn","Ansatte","Bygninger","Kraftlinjer","Toglinjer")) -> dict:
    """
    Request the consequences from the NVE API
    Args:
        polygon: GeoDataFrame with the polygon
        items: tuple with the items to request
    Returns:
        dict: consequence parameters
    """   
    gstring = poly_to_esri(polygon)
    
    consequence_items_str = '['
    for item in items:
        consequence_items_str += f'"{item}",'
    consequence_items_str = consequence_items_str[:-1] + ']'
    # print(consequence_items_str)
    params = {
        'f': 'json',  
        'in_polygon': gstring,
        'Konsekvens_typer': consequence_items_str
        } 
    response = requests.post(f"{URL}/submitJob", data=params)
    
    if response.status_code == 200:
        job_info = response.json()
        job_id = job_info['jobId']
        # print("job id: ", job_id)
    else:
        print(response.status_code)
        job_id = None
    
    
    if job_id:
        job_status_url = f"{URL}/jobs/{job_id}"
        # print("job status url: ", job_status_url)
        while True:
            response_json = check_job_status(job_id)
            status = response_json["jobStatus"]
            # print(response_json)

            if status in ['esriJobSucceeded', 'esriJobFailed']:
                break
            time.sleep(30) 
    
    if status == 'esriJobSucceeded':
        result_url = f"{job_status_url}/results/resultat"
        print("result url: ", result_url)
        response = requests.get(result_url)
        if response.status_code != 200:
            return {"error: ", response.status_code}
            
        else:
            html_content = response.content
            soup = BeautifulSoup(html_content, 'html.parser')
            body = soup.body
            
            td_pre_tags = soup.find_all('td')
            for td in td_pre_tags:
                pre_tag = td.find('pre')
                if pre_tag:
                    text_inside_pre = pre_tag.get_text()
                    data_dict = json.loads(text_inside_pre)
            
            return data_dict["value"]["konsekvensparametere"]
    else:
        return {"API error": f"see the details here: {job_status_url}"}

def report_consequence(consequence_dict: dict) -> list:
    """
    Report the consequences from the NVE API
    Args:
        consequence_dict: dict with the consequence parameters
    Returns:
        list: list with the report
    """

    output = []
    query_items = ["beboere","barnehagebarn", "skoleelever","ansatte","bygninger","veier","kraftnett","toglinjer"]
    for kk, vv in consequence_dict.items():
        if kk in query_items: output.append("\n")
        if kk != "Avviksmelding": output.append(kk)
        if kk in query_items: output.append("--------------------")
        if isinstance(vv, dict):
            oo = report_consequence(vv)
            
            if len(oo) > 0:
                output.extend(oo)
                
            if 'Avviksmelding' in vv.keys() and vv['Avviksmelding'] != "Ingen":
                output.append(f"  {vv['Avviksmelding'].encode('latin1').decode('utf-8')}")
            
        else:
            if kk != "Avviksmelding": 
                output.append(f"  {vv}")
    return output

format_dict = {
    "beboere": "Beboere",
    "antallbeboere": "Total antall beboere (minste antall er 10). <small>Kilde: Årsversjon av adressepunkt fra SSB.</small>",
    "barnehagebarn": "Barnehagebarn",
    "antallbarn": "Total antall barnehagebarn der det finnes barnehage. <small>Kilde: Utdanningsdirektoratets Nasjonale Barnehage- og Nasjonale Skoleregister.</small>",
    "skoleelever": "Skolebarn",
    "ant_elever": "Total antall skoleelever der det finnes skole. <small>Kilde: Utdanningsdirektoratets Nasjonale Barnehage- og Nasjonale Skoleregister.</small>",
    "ansatte": "Ansatte",
    "firantansatt": "Summert antall ansatte per bedriftskategori. <small>Kilde: Brønnøysundsregistrene: Enhetsregisteret og Foretaksregisteret. Merk: Når en bedrift ligger innenfor valgt område vil alle ansatte i denne bedriften medregnes i resultatet, selv om de f.eks. jobber ved et annet kontor som ligger utenfor området.</small>",
    "bygninger": "Bygninger",
    "antall": "Antallet bygninger delt inn i kategorier. <small>Kilde: FKB bygg fra statenskartverk. Betegnelsene S2/S3/F2/F3 viser til tek17 sikkerhetsklasser for skred (S) og flom (F).</small>",
    "kraftnett": "Kraftnett",
    "kraftlinjer": "Summert lengde Sentral-, Regional- og Distribusjonsnett og total antall stolper/master. <small>Kilde: NVE Kraftlinje.</small>",
    "nettnivaa_lengde": "Lengde av kraftlinjer i meter. Sentralnett (1), Regionalnett (2), Distribusjonsnett (3).</small>",
    "toglinjer": "Toglinjer",
    "baneprioritet_lengde": "Totale lengde jernbane per baneprioritets kategori. <small>Kilde: Jernbaneverket.</small>",
    
    
}

def report_consequence_html(consequence_dict:dict, level:int=2) -> list:
    """
    Report the consequences from the NVE API as html elements
    Args:
        consequence_dict: dict with the consequence parameters
        level: int with the level of the header
    Returns:
        list: list with the report
    """
    output = []
    query_items = ["beboere", "barnehagebarn", "skoleelever", "ansatte", "bygninger", "veier", "kraftnett", "toglinjer"]
    
    if level == 2:
        output.append("<html>")
        output.append("<head>")
        output.append("""
        <style>
            body {
                font-family: Arial, sans-serif;
                line-height: 0.8;
                margin: 20px;
            }

            h2.consequence-popup {
                font-size: 1em;
                color: #333;
                line-height: 1.5;
            }
            h3.consequence-popup {
                font-size: 0.9em;
                color: #333;
                line-height: 1.5;
            }
            h4.consequence-popup {
                font-size: 0.8em;
                color: #333;
                line-height: 1.5;
            }
            p.consequence-popup {
                font-size: 0.7em;
                color: #666;
                margin: 0px;
            }
            hr.consequence-popup {
                border: 0;
                height: 1px;
                background: #ccc;
                margin: 2px 0;
            }
        </style>
        """)
        output.append("</head>")
        output.append("<body>")
    
    for kk, vv in consequence_dict.items():
        if kk in query_items:
            output.append("<br>")
        if kk != "Avviksmelding":
            output.append(f"<h{level} class=consequence-popup>{format_dict.get(kk, kk)}</h{level}>")
        if kk in query_items:
            output.append("<hr class=consequence-popup>")
        if isinstance(vv, dict):
            oo = report_consequence_html(vv, level + 1)
            if len(oo) > 0:
                output.extend(oo)
            if 'Avviksmelding' in vv.keys() and vv['Avviksmelding'] != "Ingen":
                output.append(f"<p class=consequence-popup>({vv['Avviksmelding'].encode('latin1').decode('utf-8')})</p>")
            #     continue
        else:
            if kk != "Avviksmelding":
                output.append(f"<p class=consequence-popup>{vv}</p>")
    
    if level == 2:
        output.append("</body>")
        output.append("</html>")
    
    return output


def generate_html(consequence_dict:dict) -> str:
    """
    Generate the html from the consequence dict
    Args:
        consequence_dict: dict with the consequence parameters
    Returns:
        str: html string
    """
    html_lines = report_consequence_html(consequence_dict)
    return "\n".join(html_lines)


