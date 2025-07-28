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
    },
    'consequence': {
        'url': "https://gis3.nve.no/arcgis/rest/services/geoprocessing/Konsekevens1/GPServer/KonskvensParametere1",
        'items': ["Beboere","Barn","Ansatte","Bygninger","Kraftlinjer","Toglinjer"]
    },
    'nadag': {
        'url': "https://ogcapitest.ngu.no/rest/services/grunnundersokelser_utvidet/collections",
        'timeout': 300,
        'column_mapper_borehole': {
            'anvendtlast': 'penetration_force', 
            'boretlengde': 'depth', 
            'dreiemoment': 'rotation_moment', # ????
            'kombinasjonsondering': 'method_id',
            'trykksondering': 'method_id',
            'statisksondering': 'method_id',
            'nedpressinghastighet': 'penetration_rate', 
            'nedpressingtrykk': 'qc', # ???? <--- cpt
            'friksjon': 'fs', # ???? <--- cpt
            'poretrykk': 'u2', # ???? <--- cpt
            'nedpressingtid': 'penetration_time', # ????
            'observasjonkode': 'comment_code', 
            'observasjonmerknad': 'comment', 
            'rotasjonhastighet': 'rotation_rate',
            'slagfrekvens': 'hammering_rate', # ????
            'spylemengde': 'flushing_flow', 
            'spyletrykk': 'flushing_pressure',
            #'geotekniskborehullunders':'location_id',
            },
        'columns_samples': [
            'lagPosisjon', 'prøveMetode_x', 'labAnalyse', 'boretLengde_x', 'geotekniskproveseriedel', 
            'observasjonKode', 'skjærfasthetOmrørt', 'skjærfasthetUforstyrret', 'vanninnhold', 
            'aksielDeformasjon', 'skjærfasthetUdrenert', 'detaljertLagSammensetning', 'densitetPrøvetaking', 
            'flyteGrense', 'plastitetsGrense', 'prøveseriedelNavn', 'fraLengde', 'tilLengde', 'prøveseriedelId', 
            'prøveserieId', 'geotekniskborehullunders', 'geometry', 'opphav', 'høydeReferanse', 'opprettetDato', 
            'geotekniskMetode', 'boretAzimuth', 'boretHelningsgrad', 'boretLengdeTilBerg', 'undersøkelseStart', 
            'høyde', 'forboretLengde', 'stoppKode', 'forboretStartLengde', 'borenr'
        ],
        'column_mapper_samples': {
            'prøvemetode_x': 'prøvemetode',
            'boretlengde_x': 'boretlengde',
            'prøveseriedelnavn': 'name',
            # 'geotekniskborehullunders':'location_id',
            'geotekniskborehullunders':'gbhu_id',
            'prøveseriedelid': 'method_id',
            'fralengde': 'depth_top',
            'tillengde': 'depth_base',
            'skjærfasthetuforstyrret': 'strength_undisturbed',
            'skjærfasthetudrenert': 'strength_undrained',
            'skjærfasthetomrørt': 'strength_remoulded',
            'flytegrense': 'liquid_limit',
            'plastitetsgrense': 'plastic_limit',
            'vanninnhold': 'water_content',
            'høyde': 'location_elevation',
            'detaljertlagsammensetning': 'layer_composition',
            'borenr': 'location_name',
            'densitetprøvetaking': 'unit_weight',
            },
        'flag_codes': {
                      'hammering_starts': ["11", "15", "63"],
                      'hammering_ends': ["16", "64"],
                      'increased_rotation_rate_starts': ["51"],
                      'increased_rotation_rate_ends': ["52"],
                      'flushing_starts': ["14", "63"],
                      'flushing_ends': ["62", "64"],


        }
        
    },
}

def get_config():
    return config
    