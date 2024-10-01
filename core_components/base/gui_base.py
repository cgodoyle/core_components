from abc import ABC, abstractmethod
from functools import partial
import ipyvuetify
import ipywidgets
import ipyleaflet


class BtnLoader(ipyvuetify.Btn):
    """
    A custom button class that supports loading state toggling.
    Inherits from ipyvuetify.Btn.

    Attributes:
        loading (bool): Indicates whether the button is in loading state.
        disabled (bool): Indicates whether the button is disabled.

    Methods:
        toggle_loading(): Toggles the loading state of the button.
    """

    def toggle_loading(self):
        """
        Toggles the loading state of the button.
        When called, it will toggle the `loading` attribute and disable the button.
        """
        self.loading = not self.loading
        self.disabled = self.loading
    

class Loader(ipyvuetify.Container):
    def __init__(self, text="Loading..."):
        self.loader = ipyvuetify.ProgressLinear(indeterminate=True, height="12", color="red")
        self.text_widget = self.text_widget = ipywidgets.HTML(value=f"<span>{text}</span>")
        super().__init__(children=[self.loader, self.text_widget])
    
    def set_text(self, text):
        self.style_ = 'display: block;'
        self.text_widget.value = f"<span>{text}</span>"
        
    def hide(self):
        self.style_ = 'display: none;'
        self.text_widget.value = ""
    

class OutputPopup(ipyleaflet.Popup):
    """
    A custom popup class that displays an output widget. 
    It is not conected directly to the gui, only through the functions.

    Parameters:
    -----------
    map : ipyleaflet.Map
        The map object to which the popup belongs.

    Attributes:
    -----------
    same as ipyleaflet.Popup

    Methods:
    --------
    relocate_and_open()
        Clears the output widget and opens the popup at the specified location.
    """

    def __init__(self, map, **kwargs):
        super().__init__(**kwargs)

        self.m = map
        self.max_height = 500
        self.max_width = 800
        self.min_width = 500
        self.width = "auto"
        self.auto_pan = False
        self.close_button = True
        self.auto_close = True
        self.close_on_escape_key = True
        self.location = (self.m.center[0]-0.3, self.m.center[1])
        self.child = ipywidgets.Output()

    def relocate_and_open(self, clear_output=True, show=True):
        if clear_output:
            self.child.clear_output()
            
        if show:
            center = self.m.center
            bounds = self.m.bounds
            popup_location = (bounds[0][0], center[1])
            self.open_popup(popup_location)


class SideMenu(ipyvuetify.Container):
    def __init__(self, expansion_panel_items: list, grid_items: list, 
                classes: list = None, icon: str = 'mdi-menu'):
        """
        Initializes the SideMenu class with the given items and grid items.

        Args:
            expansion_panel_items (list): A list of items to be displayed in the expansion panel.
            grid_items (list): A list of items to be displayed in the grid.
            classes (list, optional): A list of CSS classes to be applied to the containers. Defaults to None.
            icon (str, optional): The icon to be displayed in the expansion panel header. Defaults to 'mdi-menu'.
        """
        super().__init__()

        self.classes = ["expansion-panel-container", "expansion-panel-header", "expansion-panel-content",
                        "grid-menu-container", "side-menu-container"] if classes is None else classes

        self.icon = icon


        expansion_panel = ipyvuetify.ExpansionPanels(children=[
            ipyvuetify.ExpansionPanel(children=[
                ipyvuetify.ExpansionPanelHeader(
                    class_=self.classes[1],
                    children=[
                    ipyvuetify.Icon(children=[self.icon])
                ]),
                ipyvuetify.ExpansionPanelContent(class_=self.classes[2],
                                                 children=[
                    ipyvuetify.Container(class_=self.classes[0], children=expansion_panel_items)
                ])
            ])
        ])

        grid_container = ipyvuetify.Container(class_=self.classes[3], children=grid_items)

        self.children = [expansion_panel, grid_container]
        self.class_ = self.classes[4]


class SimpleSideMenu(ipyvuetify.Layout):
    def __init__(self, expansion_panel_items: list, 
            classes: list = None, icon: str = 'mdi-menu'):
        """
        Initializes the SimpleSideMenu class with the given items and grid items.

        Args:
            expansion_panel_items (list): A list of items to be displayed in the expansion panel.
            grid_items (list): A list of items to be displayed in the grid.
            classes (list, optional): A list of CSS classes to be applied to the containers. Defaults to None.
            icon (str, optional): The icon to be displayed in the expansion panel header. Defaults to 'mdi-menu'.
        """
        super().__init__()

        self.classes = ["expansion-panel-header", "expansion-panel-mini-content"] if classes is None else classes

        vepc1 = ipyvuetify.ExpansionPanel(children=[
            ipyvuetify.ExpansionPanelHeader(class_="expansion-panel-header",
                                            children=[ipyvuetify.Icon(children=[icon], left=True)]),
            ipyvuetify.ExpansionPanelContent(class_="expansion-panel-mini-content",
                                            children=[expansion_panel_items])])

        vep = ipyvuetify.ExpansionPanels(children=[vepc1])


        self.children = [vep]


class WMSComponent(SimpleSideMenu):
    def __init__(self, m, wms_dict: dict):
        """
        Initializes the WMSComponent class with the given buttons and panel.

        Args:
            wms_buttons (list): A list of buttons to be displayed.
            wms_panel (ipyvuetify.Container): The panel to be displayed.
        """
        
        component_dict = {}
        for wms_name, wms_params in wms_dict.items():
            button = ipywidgets.Button(description=wms_name, layout=ipywidgets.Layout(width="auto"), icon="fa-map",
                                       tooltip=f"Add {wms_name} wms-layer")
            component_dict[wms_name] = button
            button.on_click(partial(self.action_wms_default, m=m, wms_name=wms_name, wms_params=wms_params))
        
        wms_layers_box = ipywidgets.VBox(list(component_dict.values()), layout=ipywidgets.Layout(padding="0px 5px 5px 5px"))
        super().__init__(expansion_panel_items=wms_layers_box, icon="mdi-map")
        self.items = component_dict


    @staticmethod
    def action_wms_default(b, m, wms_name, wms_params) -> None:

        for layer_i in m.layers:
            if layer_i.name == wms_name and layer_i.visible:
                layer_i.visible = False
                b.style.button_color = None
                return
            elif layer_i.name == wms_name and not layer_i.visible:
                layer_i.visible = True
                b.style.button_color = "lightgreen"
                return
        wms = ipyleaflet.WMSLayer(
            url=wms_params.get('url'),
            layers=wms_params.get('layers'),
            format=wms_params.get('format', 'image/png'),
            transparent=wms_params.get('transparent', True),
            name=wms_name,
            visible=True,
        )
        b.style.button_color = "lightgreen"
        m.add(wms)
    

class GUIBase(ABC):
    def __init__(self):
        self.buttons = self.create_buttons()
        self.sliders = self.create_sliders()
        self.checkboxes = self.create_checkboxes()
        self.outputs = self.create_outputs()
        self.other_widgets = self.create_other_widgets()
        self.side_panel = self.gui_side_panel()
        self.wms_buttons = []
        self.wms_panel = self.gui_wms_panel()
    
    @abstractmethod
    def create_buttons(self):
        ...

    @abstractmethod
    def create_sliders(self):
        ...

    @abstractmethod
    def create_checkboxes(self):
        ...

    @abstractmethod
    def create_outputs(self):
        ...

    @abstractmethod
    def gui_side_panel(self):
        ...

    @abstractmethod
    def gui_wms_panel(self):
        ...
    
    @abstractmethod
    def create_other_widgets(self):
        ...

    @staticmethod 
    def _div(tag, class_, children):
        return ipyvuetify.Html(tag=tag, class_=class_, children=children)
    
    @staticmethod
    def _create_tooltip(children, tooltip):
        return ipyvuetify.Tooltip(bottom=True, 
                                  v_slots=[{'name': 'activator','variable': 'tooltip',
                                            'children': children,}], 
                                  children=[tooltip]) 
