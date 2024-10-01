from abc import ABC, abstractmethod
from IPython.display import display, Javascript
import ipyleaflet
import ipywidgets



class ControllerBase(ABC):
    def __init__(self, map, ui):
        self.m = map
        self.fixed_layers = ['']
        self.removable_layers = ['Profiles', 'Release', 'Runout']

        self.buttons = ui.buttons
        self.sliders = ui.sliders
        self.checkboxes = ui.checkboxes
        self.download_output = ui.outputs["download_output"]
        self.other_widgets = ui.other_widgets
        display(self.download_output)

        self.side_panel = ui.side_panel
        self.wms_panel = ui.wms_panel
        self.wms_buttons = ui.wms_buttons

        self.lastimeclicked = 0


    @abstractmethod
    def bind_callbacks(self):
        pass


    @abstractmethod
    def gui_to_map(self):
        pass
    

    @abstractmethod
    def reset_savings(self):
        # self.figures_to_save = []
        # self.data_to_save = {"release": [], "source":[], "clipping": [], "runout": [], "report": []}
        pass
    

    def callback_clear_drawings(self, b, *args) -> None:

        for layer_i in self.m.layers:
            if layer_i.base or isinstance(layer_i, ipyleaflet.WMSLayer):
                continue
            elif any(layer_i.name.startswith(prefix) for prefix in self.removable_layers):
                self.m.remove(layer_i)

        self.counter = 0
        for control_i in self.m.controls:
            if type(control_i) == ipyleaflet.LegendControl:
                self.m.remove(control_i)

        self.reset_savings()

        current_click_time = args[-1]["timeStamp"]
        if current_click_time - self.lastimeclicked < 500:
            self.m.clear_drawings()

        self.lastimeclicked = current_click_time
    

    def callback_info_help(self, html_file:str, b: ipywidgets.Button, *args, **kwargs) -> None:
        
        width = kwargs.get("width", 700)
        height = kwargs.get("height", 900)
        left = kwargs.get("left", 100)
        top = kwargs.get("top", 100)

        with self.download_output:
            display(Javascript(f"""

                            var myWindow = window.open('{html_file}', '_blank', 'height={height}, width={width}, left={left}, top={top}');
                            myWindow.onblur = function() {{ this.close(); }};

                            """))
