config = {
    'global': {
        'crs_map': 4326,
        'crs_default': 25833
    },
    'hoydedata': {
        'hoydedata_layer': "NHM_DTM_25833",
        'hoydedata_url': "https://hoydedata.no/arcgis/rest/services/{}/ImageServer/exportImage?bbox={},{},{},{}&size={},{}&bboxSR=&size=&imageSR=&time=&format=tiff&pixelType=F32&noData={}&noDataInterpretation=esriNoDataMatchAny&interpolation=+RSP_BilinearInterpolation&compression=&compressionQuality=&bandIds=&mosaicRule=&renderingRule=&f=image"
    },
    'buildings': {
        'url': "https://wfs.geonorge.no/skwms1/wfs.matrikkelen-bygningspunkt",
        'columns': ['bygningsnummer', 'bygningsstatus', 'kommunenavn', 'bygningstype', 'bygningId', 'geometry'],
        'query_filter': "bygningsstatus not in ('GR', 'IP', 'BR', 'BF', 'IG')"
    }
}

def get_config():
    return config
    