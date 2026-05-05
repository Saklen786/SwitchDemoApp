import json
import threading
import time
import asyncio
import os
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.properties import StringProperty, ListProperty, BooleanProperty
from kivy.graphics import RenderContext
from kivy.core.audio import SoundLoader
from bleak import BleakScanner, BleakClient

# --- REQUEST ANDROID PERMISSIONS AT STARTUP ---
if platform == 'android':
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.BLUETOOTH_SCAN,
        Permission.BLUETOOTH_CONNECT,
        Permission.ACCESS_FINE_LOCATION,
        Permission.ACCESS_COARSE_LOCATION
    ])
# --- ANDROID ROTATION LOCK ---
# Note: To natively lock the orientation on Android devices so the layout does not rotate, 
# you MUST configure your buildozer.spec file before compiling the APK:
# Change: orientation = all  --->  To: orientation = portrait (or landscape if specifically needed)

# Set window size for Mobile Portrait testing on PC
Window.size = (400, 800)
Window.clearcolor = (0.020, 0.027, 0.039, 1) 
POSITIONS_FILE = "glow_positions.json"

# --- BLE Configuration ---
PICO_BLE_NAME = "RE_Switch_Dash"
UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E" 

# --- Custom Fragment Shader to Force Exact Image Tinting (Fixes Blue Color bug) ---
fs_shader = '''
$HEADER$
uniform vec4 tint_color;
void main(void) {
    vec4 tex_color = texture2D(texture0, tex_coord0);
    // Ignore the texture's original RGB, apply our exact tint_color RGB, and multiply the Alpha
    gl_FragColor = vec4(tint_color.rgb, tex_color.a * tint_color.a);
}
'''

class TintedImage(Image):
    tint_color = ListProperty([1, 1, 1, 1])

    def __init__(self, **kwargs):
        # Override Kivy's default canvas BEFORE super() so it adopts our shader
        self.canvas = RenderContext(use_parent_projection=True, use_parent_modelview=True)
        self.canvas.shader.fs = fs_shader
        super().__init__(**kwargs)

    def on_tint_color(self, instance, value):
        self.canvas['tint_color'] = [float(v) for v in value]

# --- Custom Draggable Image Class ---
class DraggableGlow(Image):
    glow_id = StringProperty("")

    def on_touch_down(self, touch):
        app = App.get_running_app()
        if not app.root.edit_mode:
            return super().on_touch_down(touch)
        
        if self.collide_point(*touch.pos):
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            parent = self.parent
            if parent:
                new_cx = (touch.x - parent.x) / parent.width
                new_cy = (touch.y - parent.y) / parent.height
                new_cx = max(0.0, min(1.0, new_cx))
                new_cy = max(0.0, min(1.0, new_cy))
                self.pos_hint = {'center_x': new_cx, 'center_y': new_cy}
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            App.get_running_app().root.save_positions()
            return True
        return super().on_touch_up(touch)

# --- Kivy UI Layout (Portrait Mobile) ---
KV = '''
#:import FadeTransition kivy.uix.screenmanager.FadeTransition

<NavItem@ButtonBehavior+BoxLayout>:
    orientation: 'vertical'
    icon_source: 'icon_dashboard.png' # Fallback
    text: ''
    is_about: False
    active: False
    spacing: 4
    padding: [0, 10, 0, 5]
    color_val: (1, 0.176, 0.478, 1) if self.active else (0.478, 0.522, 0.6, 1)
    
    FloatLayout:
        size_hint_y: 0.65
        
        # Icon layer (Forces opacity to 0 to prevent gray box glitch on the About tab)
        TintedImage:
            source: root.icon_source
            opacity: 0 if root.is_about else 1
            tint_color: root.color_val
            pos_hint: {'center_x': 0.5, 'center_y': 0.5}
            size_hint: (1.0, 1.0)
            keep_ratio: True
        
        # Custom Canvas-drawn (i) icon for the 'About' section
        Label:
            text: "i" if root.is_about else ""
            font_name: 'Roboto'
            font_size: '18sp'
            bold: True
            color: root.color_val
            pos_hint: {'center_x': 0.5, 'center_y': 0.5}
            canvas.before:
                Color:
                    rgba: root.color_val if root.is_about else (0,0,0,0)
                Line:
                    circle: (self.center_x, self.center_y, 14)
                    width: 1.5
    Label:
        text: root.text
        font_size: '10sp'
        color: root.color_val
        bold: root.active
        size_hint_y: 0.35

<DashboardLayout>:
    BoxLayout:
        orientation: 'vertical'
        size: root.size
        padding: [15, 15, 15, 0] # Flush bottom for nav bar
        spacing: 15

        # 1. HEADER
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: 60
            spacing: 10
            
            Image:
                source: 'ELMOS_LOGO.png'
                size_hint_x: 0.25
                allow_stretch: True
                keep_ratio: True
                
            BoxLayout:
                orientation: 'vertical'
                size_hint_x: 0.65
                Label:
                    text: "[b]E521.39 IC[/b]"
                    markup: True
                    font_size: '20sp'
                    color: 0, 0.941, 1.0, 1  # 00F0FF Neon Cyan
                    halign: 'left'
                    valign: 'bottom'
                    text_size: self.size
                Label:
                    text: "SWITCH DEMONSTRATOR"
                    font_name: 'Roboto'
                    font_size: '9sp'
                    color: 0.478, 0.522, 0.6, 1  # 7A8599 Grey
                    halign: 'left'
                    valign: 'top'
                    text_size: self.size

            AnchorLayout:
                size_hint_x: 0.1
                anchor_x: 'right'
                anchor_y: 'center'
                Image:
                    id: ble_status_dot
                    source: root.status_img
                    size_hint: (None, None)
                    size: (12, 12)

        # 2. SCREEN MANAGER
        ScreenManager:
            id: sm
            transition: FadeTransition(duration=0.15)
            
            # ----------------------------------------------------
            # SCREEN: DASHBOARD
            # ----------------------------------------------------
            Screen:
                name: 'dashboard'
                BoxLayout:
                    orientation: 'vertical'
                    spacing: 15

                    # 2a. LIVE VOLTAGE GAUGE
                    FloatLayout:
                        size_hint_y: 0.18
                        
                        Image:
                            source: 'voltage_background.png'
                            allow_stretch: True
                            keep_ratio: False
                            pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                            size_hint: (1, 1)

                        BoxLayout:
                            orientation: 'vertical'
                            pos_hint: {'x': 0.08, 'center_y': 0.5}
                            size_hint: (0.6, 0.85) # Increased size to prevent text cropping
                            
                            Label:
                                text: "SYSTEM VOLTAGE"
                                color: 1, 0.176, 0.478, 1
                                font_size: '10sp'
                                bold: True
                                size_hint_y: 0.35
                                halign: 'left'
                                valign: 'bottom'
                                text_size: self.size
                            Label:
                                id: txt_adc
                                text: "[color=#00F0FF]0.00[/color][size=20sp] [color=#7A8599]V[/color][/size]"
                                markup: True
                                font_size: '44sp' # Slightly scaled down from 50sp
                                bold: True
                                size_hint_y: 0.65
                                halign: 'left'
                                valign: 'middle' # Center aligns inside bounds to prevent bottom clipping
                                text_size: self.size
                        
                        TintedImage:
                            source: 'icon_voltage.png'
                            tint_color: 0, 0.941, 1.0, 1 # Cyan
                            size_hint: (None, None)
                            size: (44, 44)
                            pos_hint: {'right': 0.92, 'center_y': 0.5}

                    # 2b. MOTORCYCLE GRAPHICS (Fully Flexible Remaining Height)
                    FloatLayout:
                        id: moto_container
                        size_hint_y: 1.0 # Expands dynamically depending on screen limits and Terminal Collapse state

                        Image:
                            id: moto_base
                            source: 'moto_base.png'
                            pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                            allow_stretch: True
                            keep_ratio: True

                        FloatLayout:
                            size_hint: None, None
                            size: moto_base.norm_image_size
                            pos: moto_base.center_x - self.width/2, moto_base.center_y - self.height/2

                            DraggableGlow:
                                id: glow_low_left
                                glow_id: 'glow_low_left'
                                source: 'low_beam.png'
                                pos_hint: {'center_x': 0.35, 'center_y': 0.38}
                                size_hint: (0.3, 0.3)
                                opacity: 0
                            DraggableGlow:
                                id: glow_low_right
                                glow_id: 'glow_low_right'
                                source: 'low_beam.png'
                                pos_hint: {'center_x': 0.65, 'center_y': 0.38}
                                size_hint: (0.3, 0.3)
                                opacity: 0
                            DraggableGlow:
                                id: glow_high_left
                                glow_id: 'glow_high_left'
                                source: 'high_beam.png'
                                pos_hint: {'center_x': 0.29, 'center_y': 0.40}
                                size_hint: (0.3, 0.3)
                                opacity: 0
                            DraggableGlow:
                                id: glow_high_right
                                glow_id: 'glow_high_right'
                                source: 'high_beam.png'
                                pos_hint: {'center_x': 0.71, 'center_y': 0.40}
                                size_hint: (0.3, 0.3)
                                opacity: 0
                            DraggableGlow:
                                id: glow_ind_left
                                glow_id: 'glow_ind_left'
                                source: 'indicator.png'
                                pos_hint: {'center_x': 0.08, 'center_y': 0.44}
                                size_hint: (0.25, 0.25)
                                opacity: 0
                            DraggableGlow:
                                id: glow_ind_right
                                glow_id: 'glow_ind_right'
                                source: 'indicator.png'
                                pos_hint: {'center_x': 0.92, 'center_y': 0.44}
                                size_hint: (0.25, 0.25)
                                opacity: 0

                    # 2c. TERMINAL LOG (Collapsible)
                    BoxLayout:
                        orientation: 'vertical'
                        size_hint_y: None if root.data_stream_collapsed else 0.3
                        height: 54 if root.data_stream_collapsed else 100 # 100 acts as baseline when responsive
                        padding: [15, 15, 15, 15]
                        spacing: 12
                        canvas.before:
                            Color:
                                rgba: 0.086, 0.098, 0.118, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [8]
                        
                        # Header Row
                        BoxLayout:
                            orientation: 'horizontal'
                            size_hint_y: None
                            height: 24
                            
                            Label:
                                text: "DATA STREAM"
                                color: 0.75, 0.8, 0.85, 1
                                font_size: '11sp'
                                bold: True
                                font_name: 'Roboto'
                                halign: 'left'
                                valign: 'middle'
                                text_size: self.size
                            
                            # LIVE Badge
                            BoxLayout:
                                size_hint_x: None
                                width: 65
                                canvas.before:
                                    Color:
                                        rgba: 0.12, 0.14, 0.17, 1
                                    RoundedRectangle:
                                        pos: self.pos
                                        size: self.size
                                        radius: [6]
                                Label:
                                    text: "●"
                                    color: 0, 1.0, 0.541, 1
                                    font_size: '8sp'
                                    size_hint_x: 0.3
                                Label:
                                    text: "LIVE"
                                    color: 0.85, 0.9, 0.95, 1
                                    font_size: '10sp'
                                    bold: True
                                    halign: 'left'
                                    valign: 'middle'
                                    text_size: self.size
                                    size_hint_x: 0.7
                                    
                            # Data Stream Collapse Toggle (Fixed Missing Glyph error)
                            Button:
                                text: "HIDE" if not root.data_stream_collapsed else "SHOW"
                                font_name: 'Roboto'
                                font_size: '10sp'
                                bold: True
                                size_hint_x: None
                                width: 40
                                background_normal: ''
                                background_color: 0,0,0,0
                                color: 0.478, 0.522, 0.6, 1
                                on_release: root.data_stream_collapsed = not root.data_stream_collapsed

                        # Log Scrolling Area (Hides when Collapsed)
                        ScrollView:
                            id: log_scroll
                            do_scroll_x: False
                            opacity: 0 if root.data_stream_collapsed else 1
                            disabled: root.data_stream_collapsed
                            size_hint_y: None if root.data_stream_collapsed else 1
                            height: 0 if root.data_stream_collapsed else self.parent.height
                            
                            BoxLayout:
                                orientation: 'vertical'
                                size_hint_y: None
                                height: self.minimum_height
                                Label:
                                    id: txt_log
                                    text: ""
                                    markup: True
                                    font_name: 'Roboto'
                                    font_size: '11sp'
                                    line_height: 1.5
                                    halign: 'left'
                                    valign: 'top'
                                    size_hint_y: None
                                    height: self.texture_size[1]
                                    text_size: self.width, None

            # ----------------------------------------------------
            # SCREEN: SETTINGS
            # ----------------------------------------------------
            Screen:
                name: 'settings'
                BoxLayout:
                    orientation: 'vertical'
                    spacing: 20
                    padding: [20, 30, 20, 30] # Proper horizontal alignment padding
                    
                    Label:
                        text: "SYSTEM SETTINGS"
                        color: 1, 0.176, 0.478, 1
                        font_size: '16sp'
                        bold: True
                        size_hint_y: None
                        height: 30
                        halign: 'left'
                        valign: 'middle'
                        text_size: self.size

                    BoxLayout:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: 160
                        padding: [25, 25, 25, 25]
                        spacing: 15
                        canvas.before:
                            Color:
                                rgba: 0.086, 0.098, 0.118, 1 # Premium dark card styling
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [10]
                        
                        Label:
                            text: "UI Alignment Configuration"
                            color: 0.85, 0.9, 0.95, 1
                            font_size: '14sp'
                            bold: True
                            size_hint_y: 0.4
                            halign: 'left'
                            valign: 'bottom'
                            text_size: self.size
                            
                        Label:
                            text: "Calibrate HUD overlays"
                            color: 0.478, 0.522, 0.6, 1
                            font_size: '11sp'
                            size_hint_y: 0.2
                            halign: 'left'
                            valign: 'top'
                            text_size: self.size
                            
                        Button:
                            text: "EDIT POSITIONS"
                            size_hint_y: 0.6
                            font_size: '13sp'
                            bold: True
                            background_normal: ''
                            background_color: 0, 0, 0, 0
                            color: 0, 0.941, 1.0, 1
                            on_release: root.trigger_dev_menu()
                            canvas.before:
                                Color:
                                    rgba: 0, 0.941, 1.0, 1
                                Line:
                                    rounded_rectangle: [self.x, self.y, self.width, self.height, 6]
                                    width: 1.2
                                Color:
                                    rgba: 0, 0.941, 1.0, 0.15 if self.state == 'down' else 0
                                RoundedRectangle:
                                    pos: self.pos
                                    size: self.size
                                    radius: [6]
                    
                    Widget: # Filler
                        size_hint_y: 1

            # ----------------------------------------------------
            # SCREEN: ABOUT
            # ----------------------------------------------------
            Screen:
                name: 'about'
                BoxLayout:
                    orientation: 'vertical'
                    spacing: 20
                    padding: [20, 30, 20, 30]

                    Label:
                        text: "SYSTEM INFO"
                        color: 1, 0.176, 0.478, 1
                        font_size: '16sp'
                        bold: True
                        size_hint_y: None
                        height: 30
                        halign: 'left'
                        valign: 'middle'
                        text_size: self.size

                    BoxLayout:
                        orientation: 'vertical'
                        size_hint_y: None
                        height: 220
                        padding: [25, 25, 25, 25]
                        spacing: 15
                        canvas.before:
                            Color:
                                rgba: 0.086, 0.098, 0.118, 1
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [10]
                                
                        Image:
                            source: 'ELMOS_LOGO.png'
                            size_hint_y: 0.4
                            keep_ratio: True
                            
                        Label:
                            text: "[b]E521.39 Switch Demonstrator[/b]\\nVersion 1.0.0\\n\\nDeveloped by SSAY."
                            markup: True
                            color: 0.478, 0.522, 0.6, 1
                            font_size: '13sp'
                            halign: 'center'
                            valign: 'middle'
                            size_hint_y: 0.6
                            text_size: self.size
                    
                    Widget: # Filler
                        size_hint_y: 1

        # 3. BLE CONNECT BUTTON
        FloatLayout:
            size_hint_y: None
            height: 65
            
            Image:
                source: 'ble_background.png'
                allow_stretch: True
                keep_ratio: False
                pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                size_hint: (1, 1)
            
            BoxLayout:
                orientation: 'horizontal'
                pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                size_hint: (None, None)
                size: self.minimum_size
                spacing: 12
                
                TintedImage:
                    source: 'icon_bluetooth.png'
                    size_hint: (None, None)
                    size: (34, 34)
                    tint_color: root.btn_color
                    pos_hint: {'center_y': 0.5}
                    
                Label:
                    text: root.btn_text
                    font_size: '16sp'
                    bold: True
                    color: 1, 1, 1, 1
                    size_hint: (None, None)
                    size: self.texture_size
                    pos_hint: {'center_y': 0.5}
            
            Button:
                background_color: 0, 0, 0, 0
                pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                size_hint: (1, 1)
                on_release: root.toggle_ble()

        # 4. BOTTOM NAV BAR
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: 70
            canvas.before:
                Color:
                    rgba: 0.043, 0.059, 0.078, 1 
                Rectangle:
                    pos: self.x - 15, self.y
                    size: self.width + 30, self.height
                Color:
                    rgba: 0.102, 0.122, 0.165, 1
                Line:
                    points: [self.x - 15, self.top, self.right + 15, self.top]
                    width: 1.2

            NavItem:
                icon_source: 'icon_dashboard.png'
                text: 'DASHBOARD'
                active: sm.current == 'dashboard'
                on_release: sm.current = 'dashboard'
            NavItem:
                icon_source: 'icon_setting.png'
                text: 'SETTINGS'
                active: sm.current == 'settings'
                on_release: sm.current = 'settings'
            NavItem:
                text: 'ABOUT'
                is_about: True
                active: sm.current == 'about'
                on_release: sm.current = 'about'
'''

class DashboardLayout(FloatLayout):
    btn_text = StringProperty("CONNECT BLE")
    btn_color = ListProperty([0, 0.941, 1.0, 1]) # 00F0FF Neon Cyan
    status_img = StringProperty("status_red.png")
    edit_mode = BooleanProperty(False)
    data_stream_collapsed = BooleanProperty(False) # Collapsible Data Stream Tracker

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_connected = False
        self.ble_client = None
        self.ble_loop = None
        self.log_lines = [] 
        
        self.current_ind_state = "none"
        self.blink_on = False
        self.glow_ids = ['glow_low_left', 'glow_low_right', 'glow_high_left', 'glow_high_right', 'glow_ind_left', 'glow_ind_right']
        
        self.pending_state_int = 6
        self.current_state_int = 6
        self.debounce_event = None
        self.last_logged_state = None
        
        self.last_volts = 0.0
        self.current_volt_color = "00F0FF"
        
        # Audio Setup
        self.sound_start = SoundLoader.load('two_wheeler_start.mp3')
        self.sound_horn = SoundLoader.load('horn.mp3')
        self.is_horn_active = False
        
        if self.sound_start:
            self.sound_start.loop = True
        
        Clock.schedule_interval(self.blink_loop, 0.5)
        Clock.schedule_once(self.load_positions, 0.1)
        
        # Initial Log state
        self.log_data("SYSTEM ENGAGED...")
        self.log_data("AWAITING DATA LINK...")

    # --- DEV MENU / PASSWORD SYSTEM ---
    def trigger_dev_menu(self):
        if self.edit_mode:
            self.toggle_edit_mode()
            self.save_positions()
            return
            
        content = BoxLayout(orientation='vertical', padding=15, spacing=15)
        status_lbl = Label(text='ENTER DEV OVERRIDE PIN', color=(0, 0.941, 1.0, 1))
        pwd_input = TextInput(password=True, multiline=False, font_size='24sp', halign='center', size_hint_y=None, height=50)
        
        btn_box = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50)
        btn_unlock = Button(text='UNLOCK', background_color=(0, 0.941, 1.0, 1), color=(0.043, 0.059, 0.078, 1), bold=True)
        btn_cancel = Button(text='CANCEL', background_color=(0.102, 0.122, 0.165, 1))
        btn_box.add_widget(btn_unlock)
        btn_box.add_widget(btn_cancel)
        
        content.add_widget(status_lbl)
        content.add_widget(pwd_input)
        content.add_widget(btn_box)
        
        self.popup = Popup(
            title='SYSTEM ACCESS', 
            content=content, 
            size_hint=(0.8, 0.35), 
            auto_dismiss=False,
            background_color=(0.043, 0.059, 0.078, 1),
            title_color=(0, 0.941, 1.0, 1)
        )
        
        def verify_pwd(instance):
            if pwd_input.text == "1234":
                self.toggle_edit_mode()
                self.popup.dismiss()
                self.ids.sm.current = 'dashboard'
            else:
                status_lbl.text = "INVALID PIN"
                status_lbl.color = (1, 0.176, 0.478, 1)
                pwd_input.text = ""
                
        btn_unlock.bind(on_release=verify_pwd)
        btn_cancel.bind(on_release=self.popup.dismiss)
        self.popup.open()

    def toggle_edit_mode(self):
        self.edit_mode = not self.edit_mode
        if self.edit_mode:
            self.log_data("[color=#00FF8A]→[/color] EDIT MODE ENABLED")
            for g_id in self.glow_ids:
                Animation.cancel_all(self.ids[g_id])
                self.ids[g_id].opacity = 0.8
        else:
            self.log_data("[color=#00FF8A]→[/color] EDIT MODE DISABLED")
            for g_id in self.glow_ids:
                self.ids[g_id].opacity = 0.0

    def load_positions(self, dt=None):
        if os.path.exists(POSITIONS_FILE):
            try:
                with open(POSITIONS_FILE, "r") as f:
                    data = json.load(f)
                    for g_id, pos in data.items():
                        if g_id in self.ids:
                            self.ids[g_id].pos_hint = pos
                self.log_data("ALIGNMENT DATA LOADED [OK]")
            except Exception as e:
                self.log_data(f"ERR LOADING ALIGNMENT: {e}")

    def save_positions(self):
        data = {}
        for g_id in self.glow_ids:
            widget = self.ids.get(g_id)
            if widget and widget.pos_hint:
                data[g_id] = widget.pos_hint
        try:
            with open(POSITIONS_FILE, "w") as f:
                json.dump(data, f, indent=4)
            self.log_data("NEW POSITIONS SAVED [OK]")
        except Exception as e:
            pass

    def log_data(self, msg):
        # Using a > to guarantee native rendering on all mobile fonts while keeping the aesthetic
        formatted = f"[color=#00F0FF][b]>[/b][/color]   [color=#9BA4B5]{msg}[/color]"
        self.log_lines.append(formatted)
        if len(self.log_lines) > 30: 
            self.log_lines.pop(0)
            
        if 'txt_log' in self.ids:
            self.ids.txt_log.text = '\n'.join(self.log_lines)
            Clock.schedule_once(lambda dt: setattr(self.ids.log_scroll, 'scroll_y', 0), 0.1)

    def crossfade_light(self, image_id, turn_on):
        if self.edit_mode: return 
        target_opacity = 1.0 if turn_on else 0.0
        widget = self.ids[image_id]
        if widget.opacity != target_opacity:
            anim = Animation(opacity=target_opacity, duration=0.15)
            anim.start(widget)

    def map_enum_to_state(self, state_int):
        s = {"headlight": "dipper", "pass": False, "indicator": "none", "horn": False, "warn": False}
        if state_int == 0: s["headlight"] = "upper"
        elif state_int == 1: s["headlight"] = "upper"; s["indicator"] = "right"
        elif state_int == 2: s["headlight"] = "upper"; s["indicator"] = "left"
        elif state_int == 3: s["headlight"] = "upper"; s["horn"] = True
        elif state_int == 4: s["headlight"] = "upper"; s["indicator"] = "right"; s["horn"] = True
        elif state_int == 5: s["headlight"] = "upper"; s["indicator"] = "left"; s["horn"] = True
        elif state_int == 6: s["headlight"] = "dipper"
        elif state_int == 7: s["headlight"] = "dipper"; s["pass"] = True
        elif state_int == 8: s["headlight"] = "dipper"; s["indicator"] = "right"
        elif state_int == 9: s["headlight"] = "dipper"; s["pass"] = True; s["indicator"] = "right"
        elif state_int == 10: s["headlight"] = "dipper"; s["indicator"] = "left"
        elif state_int == 11: s["headlight"] = "dipper"; s["pass"] = True; s["indicator"] = "left"
        elif state_int == 12: s["headlight"] = "dipper"; s["horn"] = True
        elif state_int == 13: s["headlight"] = "dipper"; s["pass"] = True; s["horn"] = True
        elif state_int == 14: s["headlight"] = "dipper"; s["indicator"] = "right"; s["horn"] = True
        elif state_int == 15: s["headlight"] = "dipper"; s["indicator"] = "left"; s["horn"] = True
        elif state_int == 16: s["warn"] = True
        else: s["warn"] = True 
        return s

    def update_dashboard(self, state):
        headlight = state.get("headlight", "dipper")
        ind = state.get("indicator", "none")
        horn = state.get("horn", False)
        warn = state.get("warn", False)

        if warn: self.current_volt_color = "FF2D7A"
        elif horn: self.current_volt_color = "FF2D7A"
        else: self.current_volt_color = "00F0FF"

        volts = state.get("adc_volts", self.last_volts)
        self.ids.txt_adc.text = f"[color=#{self.current_volt_color}]{volts:.2f}[/color][size=20sp] [color=#7A8599]V[/color][/size]"

        is_upper = (headlight == "upper" or state.get("pass", False))
        self.crossfade_light('glow_high_left', is_upper)
        self.crossfade_light('glow_high_right', is_upper)
        
        is_dipper = (headlight == "dipper")
        self.crossfade_light('glow_low_left', is_dipper)
        self.crossfade_light('glow_low_right', is_dipper)

        self.current_ind_state = ind

        # Handle Horn Sound Playback Trigger
        if horn and not self.is_horn_active:
            self.is_horn_active = True
            if self.sound_horn:
                self.sound_horn.play()
        elif not horn and self.is_horn_active:
            self.is_horn_active = False
            if self.sound_horn:
                self.sound_horn.stop()

    def blink_loop(self, dt):
        if self.current_ind_state != "none":
            self.blink_on = not self.blink_on
            self.crossfade_light('glow_ind_left', self.current_ind_state == "left" and self.blink_on)
            self.crossfade_light('glow_ind_right', self.current_ind_state == "right" and self.blink_on)
        else:
            self.blink_on = False
            self.crossfade_light('glow_ind_left', False)
            self.crossfade_light('glow_ind_right', False)

    # --- BLUETOOTH ENGINE ---
    def toggle_ble(self):
        if self.edit_mode:
            self.log_data("ERR: EXIT EDIT MODE BEFORE SCANNING")
            return
            
        if not self.is_connected:
            self.btn_text = "SCANNING..."
            self.btn_color = [0, 1.0, 0.541, 1] 
            self.status_img = "status_yellow.png"
            
            # Play Connection Audio Loop
            if self.sound_start:
                self.sound_start.play()
                
            threading.Thread(target=self.start_ble_engine, daemon=True).start()
        else:
            if self.ble_loop and self.ble_client:
                asyncio.run_coroutine_threadsafe(self.ble_client.disconnect(), self.ble_loop)

    def start_ble_engine(self):
        self.ble_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ble_loop)
        self.ble_loop.run_until_complete(self.run_ble_connection())

    async def run_ble_connection(self):
        try:
            Clock.schedule_once(lambda dt: self.log_data(f"SEARCHING: '{PICO_BLE_NAME}'"))
            device = await BleakScanner.find_device_by_name(PICO_BLE_NAME, timeout=10.0)
            
            if not device:
                Clock.schedule_once(lambda dt: self.log_data("ERR: PICO NOT FOUND."))
                self.reset_ble_ui()
                return

            Clock.schedule_once(lambda dt: self.log_data(f"FOUND: {device.address}"))
            self.ble_client = BleakClient(device, disconnected_callback=self.on_ble_disconnect)
            await self.ble_client.connect()

            self.is_connected = True
            Clock.schedule_once(lambda dt: self.set_ble_ui_connected())
            
            await self.ble_client.start_notify(UART_TX_CHAR_UUID, self.ble_rx_handler)
            
            while self.ble_client.is_connected:
                await asyncio.sleep(1)

        except Exception as e:
            err_msg = str(e)
            Clock.schedule_once(lambda dt, err=err_msg: self.log_data(f"BLE ERR: {err}"))
            self.reset_ble_ui()

    def on_ble_disconnect(self, client):
        self.is_connected = False
        Clock.schedule_once(lambda dt: self.log_data("BLE LINK SEVERED."))
        Clock.schedule_once(lambda dt: self.reset_ble_ui())
        
    def set_ble_ui_connected(self):
        self.log_data("BLE CONNECTED.")
        self.btn_text = "DISCONNECT"
        self.btn_color = [1, 0.176, 0.478, 1] 
        self.status_img = "status_green.png"
        if getattr(self, 'sound_start', None) and self.sound_start.state == 'play':
            self.sound_start.stop()

    def reset_ble_ui(self):
        self.is_connected = False
        self.btn_text = "CONNECT BLE"
        self.btn_color = [0, 0.941, 1.0, 1]
        self.status_img = "status_red.png"
        self.update_dashboard(self.map_enum_to_state(6))
        if getattr(self, 'sound_start', None) and self.sound_start.state == 'play':
            self.sound_start.stop()

    def ble_rx_handler(self, sender, data):
        try:
            decoded_str = data.decode('utf-8').strip()
            if not decoded_str: return
            
            payload = json.loads(decoded_str)
            state_int = payload.get("state", 16)
            volts = payload.get("adc_volts", 0.0)
            
            Clock.schedule_once(lambda dt: self.process_rx_debounced(state_int, volts, decoded_str))
        except Exception as e:
            pass 

    def process_rx_debounced(self, state_int, volts, decoded_str):
        self.last_volts = volts
        self.ids.txt_adc.text = f"[color=#{self.current_volt_color}]{volts:.2f}[/color][size=20sp] [color=#7A8599]V[/color][/size]"

        if state_int != self.pending_state_int:
            self.pending_state_int = state_int
            if self.debounce_event:
                self.debounce_event.cancel()
            
            debounce_time = 0.03 
            noisy_transitions = [{10, 11}, {8, 9}, {12, 3}, {13, 3}, {14, 3}, {15, 3}]
            if {self.current_state_int, state_int} in noisy_transitions:
                debounce_time = 0.25 
            
            self.debounce_event = Clock.schedule_once(lambda dt, s=state_int, v=volts, raw=decoded_str: self.commit_state(s, v, raw), debounce_time)
        elif not self.debounce_event:
            self.commit_state(state_int, volts, decoded_str)

    def commit_state(self, state_int, volts, decoded_str):
        self.debounce_event = None
        self.current_state_int = state_int 
        
        if getattr(self, 'last_logged_state', None) != state_int:
            self.log_data(f"RX: {decoded_str}")
            self.last_logged_state = state_int
            
        logical_state = self.map_enum_to_state(state_int)
        logical_state["adc_volts"] = volts
        self.update_dashboard(logical_state)

class MotoDashApp(App):
    def build(self):
        Builder.load_string(KV)
        return DashboardLayout()

if __name__ == '__main__':
    MotoDashApp().run()
