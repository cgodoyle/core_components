import ipyleaflet
from shapely.geometry import LineString, Polygon, box
import numpy as np
import geopandas as gpd


from core_components.base.gui_base import WMSComponent

BASE_WMS = {'Faresoner': {'url': 'https://nve.geodataonline.no/arcgis/services/SkredKvikkleire2/MapServer/WMSServer', 
                          'layers': 'KvikkleireFaregrad'},
            'Aktsomhetsomr. kvkl': 
            {'url': 'https://nve.geodataonline.no/arcgis/services/KvikkleireskredAktsomhet/MapServer/WMSServer', 
             'layers':  "KvikkleireskredAktsomhet"},
            'NADAG': {'url': "http://geo.ngu.no/geoserver/nadag/wms", 
                      'layers': "GB_standard,GBU_clustered_50px_nolimit", }
            }

class Map(ipyleaflet.Map):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.color_polyline = "#00F"
        self.color_polygon = "#cfffd2"
        
        
        self.layout.width = "100%"
        self.layout.height = "100%"
        self.center = [60.099, 11.122] if "center" not in kwargs else kwargs["center"]
        self.zoom = 10 if "zoom" not in kwargs else kwargs["zoom"]
        self.scroll_wheel_zoom=True

        self.layers = self.basemap_layers()
                
        self.map_draw_control = self.setup_draw_control()
        
        self.add(self.map_draw_control)
        
        self.add(ipyleaflet.LayersControl(position="topright"))
        self.add(ipyleaflet.FullScreenControl(position="topleft"))
        self.add(ipyleaflet.SearchControl(url="https://nominatim.openstreetmap.org/search?format=json&q={s}",
                                          zoom=17,
                                          marker=ipyleaflet.Marker()))
        self.add(ipyleaflet.ScaleControl(position="bottomleft", max_width=200, imperial=False))
        
        wms_layers = kwargs.get("wms_layers", BASE_WMS)
        self._add_wms(wms_layers)
        
    def setup_draw_control(self) -> ipyleaflet.DrawControl:
        map_draw_control = ipyleaflet.DrawControl(
        polyline={"shapeOptions": {"color": self.color_polyline}},
        polygon={"shapeOptions": {"fillColor": self.color_polygon, "fillOpacity": 0.5, "color": "black", "weight": 2}},
            position="topleft",
        )
        map_draw_control.edit = True
        map_draw_control.rectangle = {}
        map_draw_control.circlemarker = {}
        
        return map_draw_control
        

    def clear_drawings(self):
        self.map_draw_control.clear_polylines()
        self.map_draw_control.clear_polygons()
    
    def _add_wms(self, wms_dict: dict):
        self.wms_component = WMSComponent(self, wms_dict)
        wms_widget = ipyleaflet.WidgetControl(widget=self.wms_component, position="bottomleft")
        self.add(wms_widget)
    

    def get_polylines(self, name=None):
        data = self.map_draw_control.data
        for dd in data:
            if "name" not in dd.keys():
                dd["name"] = "profile"
        if name is None:
            lines = [LineString(xx['geometry']["coordinates"]) for xx in data if xx['geometry']["type"] == 'LineString']
        else:
            lines = [LineString(xx['geometry']["coordinates"]) for xx in data if xx['geometry']["type"] == 'LineString' and xx['name'] == name]
        return lines


    def get_polygons(self):
        data = self.map_draw_control.data
        polygons = [Polygon(np.squeeze(xx['geometry']["coordinates"])) for xx in data if xx['geometry']["type"] == 'Polygon']
        return polygons
    

    def get_total_bounds(self, crs=25833):
        bounds = self.bounds
        return gpd.GeoDataFrame(geometry=[box(bounds[0][1], bounds[0][0], bounds[1][1], bounds[1][0])], crs=4326).to_crs(crs).total_bounds


    @staticmethod
    def basemap_layers() -> list:
        """
        Returns the basemap layers
        """
        gcbilder = ipyleaflet.TileLayer(
            url="https://services.geodataonline.no/arcgis/rest/services/Geocache_WMAS_WGS84/"
                "GeocacheBilder/MapServer/tile/{z}/{y}/{x}",
            name="Bilde", attribution="Geodata AS")
        gcbilder.base = True

        basis = ipyleaflet.TileLayer(
            url="https://services.geodataonline.no/arcgis/rest/services/Geocache_WMAS_WGS84/"
                "GeocacheBasis/MapServer/tile/{z}/{y}/{x}",
            attribution="Geodata AS", name="Basis", format="image/png")
        basis.base = True

        osm = ipyleaflet.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attribution="OpenStreetMap",
                        name="OpenStreetMap", )
        osm.base = True

        hillshade = ipyleaflet.TileLayer(url="https://services.geodataonline.no/arcgis/rest/services/Geocache_WMAS_WGS84/"
                            "GeocacheTerrengskygge/MapServer/tile/{z}/{y}/{x}",
                            attribution="Geodata AS", name="Terrengskygge", format="image/png")
        hillshade.base = True

        return [osm, gcbilder, basis]


    def draw_polylines(self, gdf:gpd.GeoDataFrame, crs=25833, name="profile", center_on_drawing=False)->None:
        #TODO: Geometry check

        # print(self.map_draw_control.data)
        features = []#self.map_draw_control.data # before it was an empty list
        for profile in gdf.itertuples():
            coordinates = [list(xx) for xx in list(profile.geometry.coords)]
            features.append(
                {'type': 'Feature',
                'properties': {
                    'style': {
                        'stroke': True,
                        'color': '#3388ff' if name == "profile" else '#ff0000',
                        'weight': 4,
                        'opacity': 0.5,
                        'fill': False,
                        'clickable': True
                        }
                        },
                'geometry': {
                    'type': 'LineString',
                    'coordinates': coordinates},
                'name': name
                }
            )
             
        self.map_draw_control.data = features
        if center_on_drawing:
            self.center=gdf.dissolve().to_crs(crs).representative_point().to_crs(4326).get_coordinates().values.squeeze().tolist()[::-1]
            self.zoom = 15


    def show(self, height: int = 600) -> None:
        
        from ipyvuetify import Container
        from IPython.display import display
        
        layout = Container(
            class_='app-map-container', 
            style_ = f"height: {height}px;",
            children=[self])

        display(layout)
