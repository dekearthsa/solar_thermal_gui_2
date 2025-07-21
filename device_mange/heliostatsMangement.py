from kivy.uix.gridlayout import GridLayout
import os
import json
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
import json
from functools import partial
from .fileChooserPopup import FileChooserPopup 
from kivy.metrics import dp

CONN_PATH = './data/setting/connection.json'

class HeliostatsMangement(Screen):

    SAVE_DIR = os.path.join(os.getcwd(), 'data', 'setting')
    SAVE_FILE = 'connection.json'
    SAVE_PATH = os.path.join(SAVE_DIR, SAVE_FILE)
    # heliostats_data = ListProperty([])
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Clock.schedule_once(lambda dt: self.get_all_list_of_heliostats())
        
    def on_enter(self):          
        self.get_all_list_of_heliostats()

    def open_file_dialog(self):
        content = FileChooserPopup(load=self.load, cancel=self.dismiss_popup)
        self._popup = Popup(title="Select JSON File",
                            content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()

    def __check__list_connection(self, data):
        print(data)
        if data['helio_stats_ip']:
            if data['camera_url']:
                return True
            else:
                return False
        else:
            return False


    def load(self, path, selection):
        if selection:
            selected_path = selection[0]
            try:
                with open(selected_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                is_format = self.__check__list_connection(data)
                if is_format == True:
                    self.display_json(data)
                    self.save_json(data)
                    self.dismiss_popup()
                    self.show_popup("Success", f'JSON saved to {self.SAVE_PATH}')
                else:
                    self.show_popup("Invalid json format", f'Invalid json format!')
            
            except json.JSONDecodeError as jde:
                self.show_popup("JSON Error", f"Invalid JSON file:\n{str(jde)}")
            except Exception as e:
                self.show_popup("Invalid json format", f'Invalid json format! \n{str(data)}')

        else:
            # print("No")
            self.show_popup("Selection Error", "No file selected.")

    def dismiss_popup(self):
        if self._popup:
            self._popup.dismiss()

    def display_json(self, data, parent=None, indent=0):
        if parent is None:
            parent = self.ids.json_display
            parent.clear_widgets()

        if isinstance(data, dict):
            for key, value in data.items():
                label = Label(
                    text=f"{'  ' * indent}{key}: {self.format_value(value)}",
                    size_hint_y=None,
                    height=self.calculate_label_height(value),
                    halign='left',
                    valign='middle'
                )
                label.bind(size=label.setter('text_size'))
                parent.add_widget(label)
                if isinstance(value, (dict, list)):
                    self.display_json(value, parent, indent + 1)
        elif isinstance(data, list):
            for index, item in enumerate(data):
                label = Label(
                    text=f"{'  ' * indent}[{index}]: {self.format_value(item)}",
                    size_hint_y=None,
                    height=self.calculate_label_height(item),
                    halign='left',
                    valign='middle'
                )
                label.bind(size=label.setter('text_size'))
                parent.add_widget(label)
                if isinstance(item, (dict, list)):
                    self.display_json(item, parent, indent + 1)

    def format_value(self, value):
        if isinstance(value, (dict, list)):
            return ''
        return str(value)

    def calculate_label_height(self, value):
        if isinstance(value, (dict, list)):
            return '20dp'
        else:
            return '30dp'

    def save_json(self, data):
        try:
            os.makedirs(self.SAVE_DIR, exist_ok=True)
            with open(self.SAVE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.show_popup("Save Error", f"Failed to save JSON:\n{str(e)}")

    def show_popup(self, title, message):
        popup_content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        popup_label = Label(text=message)
        popup_button = Button(text="OK", size_hint=(1, 0.3))
        popup_content.add_widget(popup_label)
        popup_content.add_widget(popup_button)

        popup = Popup(title=title,
                        content=popup_content,
                        size_hint=(0.6, 0.4))
        popup_button.bind(on_release=popup.dismiss)
        popup.open()

    
    def get_all_list_of_heliostats(self):
        self.ids.heliostats_input.text =""
        self.ids.address_input.text =""
        with open(CONN_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)

        helios = data.get('helio_stats_ip', [])
        parent = self.ids.helio_list
        parent.clear_widgets()

        for idx, item in enumerate(helios):
            if item['id'] == 'all':
                continue   # ไม่ให้ลบรายการ all

            # ► แถวละ 2 คอลัมน์
            row = GridLayout(cols=2,size_hint_y=None,
                             height=dp(30),
                             spacing=10)

            # ▸ Label
            lbl = Label(
                text=f"ID: {item['id']}  |  IP: {item['ip']}",
                halign='left', valign='middle'
            )
            lbl.bind(size=lbl.setter('text_size'))
            row.add_widget(lbl)

            # ▸ Button — ใช้ partial ส่ง id/idx เข้า callback
            btn = Button(text='Delete',size_hint=(0.25, 1))
            btn.bind(on_press=partial(self.handle_remove, item['id']))
            row.add_widget(btn)

            # ดันทั้งแถวใส่ BoxLayout
            parent.add_widget(row)

    # ----------------- LOGIC -----------------
    def handle_remove(self, target_id, *args):
        """ลบรายการออกจากไฟล์ ตาม id แล้วรีเฟรชจอ"""
        if not os.path.exists(CONN_PATH):
            return

        with open(CONN_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)

        helios = data.get('helio_stats_ip', [])
        new_helios = [h for h in helios if h['id'] != target_id]

        # ถ้าไม่มีอะไรเปลี่ยน ไม่ต้องเขียนทับ
        if len(new_helios) == len(helios):
            return

        data['helio_stats_ip'] = new_helios
        with open(CONN_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

        # โหลดรายการใหม่ให้ผู้ใช้เห็นทันที
        self.get_all_list_of_heliostats()

    def on_adding_heliostats(self):
        heliostats_id = self.ids.heliostats_input.text 
        ip_address = self.ids.address_input.text
        if heliostats_id == "" and ip_address == "": 
            self.show_popup(title="Alert", message="Cannot add empty ID and Address.")
        payload = {
            "id": heliostats_id.strip(),
            "ip": ip_address.strip()
        }

        with open(CONN_PATH, 'r', encoding='utf-8') as rd:
            list_conn = json.load(rd)
        
        list_conn['helio_stats_ip'].append(payload)
        print(list_conn)
        with open(CONN_PATH, 'w', encoding='utf-8') as f:
            json.dump(list_conn, f, indent=4)
        self.get_all_list_of_heliostats()

    # def refresh_heliostats_list(self):
    #     parent = self.ids.helio_list
    #     parent.clear_widgets()

    #     self.ids.heliostats_input.text =""
    #     self.ids.address_input.text =""

    #     with open(CONN_PATH, 'r', encoding='utf-8') as rd:
    #         list_conn = json.load(rd)

    #     for item in list_conn.get('helio_stats_ip', []):
    #         if item['id'] != 'all':
    #             grid = GridLayout(cols=2, spacing=10, size_hint_y=None, height=30)
    #             label = Label(
    #                 text=f"ID: {item['id']} | IP: {item['ip']}",
    #                 size_hint_y=None,
    #                 height=30
    #             )
    #             delete_btn = Button(
    #                 text='Delete',
    #                 size_hint=(0.2, 1),
    #                 on_press=lambda x, i=item: self.remove_heliostat(i)  # ส่ง item ไปให้ลบ
    #             )
    #             grid.add_widget(label)
    #             grid.add_widget(delete_btn)
    #             parent.add_widget(grid)

    def haddle_off_get_data(self):
        pass

    def call_close_camera(self):
        pass

    def stop_fetch_loop(self):
        pass

 