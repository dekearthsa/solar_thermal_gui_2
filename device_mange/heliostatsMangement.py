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
from kivy.metrics import dp
from kivy.clock import Clock

CONN_PATH = './data/setting/connection.json'

class HeliostatsMangement(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(lambda dt: self.get_all_list_of_heliostats())
        
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
        camera_addrs = data.get('camera_url', [])
        parent = self.ids.helio_list
        parent.clear_widgets()
        self.ids.camera_address_val.text = camera_addrs[0]['url']
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
        # print(list_conn)
        with open(CONN_PATH, 'w', encoding='utf-8') as f:
            json.dump(list_conn, f, indent=4)
        self.get_all_list_of_heliostats()


    def haddle_off_get_data(self):
        pass

    def call_close_camera(self):
        pass

    def stop_fetch_loop(self):
        pass

    def haddle_update_camera(self):
        cam_addr = self.ids.camera_address_val.text
        with open(CONN_PATH, 'r') as f:
            camera_conn_list = json.load(f)

        for item in camera_conn_list['camera_url']:
            item['url'] = cam_addr.strip()

        with open(CONN_PATH, 'w') as wf:
            json.dump(camera_conn_list,wf,indent=4)