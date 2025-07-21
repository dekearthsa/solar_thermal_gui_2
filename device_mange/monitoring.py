import json
import cv2
import numpy as np
from kivy.clock import Clock

from kivy.graphics.texture import Texture
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.core.image import Image as CoreImage
import requests
from datetime import datetime
import os

class Monitoring(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.capture = None
        Clock.schedule_once(lambda dt: self.fetch_all_helio_cam())
        

        #### IN DEBUG MODE CHANGE THRES HERE ####
        self.static_low_h = 0 #10
        self.static_low_s = 0
        self.static_low_v = 180
        self.static_high_h = 179
        self.static_high_s = 255
        self.static_high_v = 255
        self.static_blur_kernel = (55,55) 
        self.static_min_area = 50000
        self.camera_connection = "./test_video.avi"
        # self.helio_stats_connection = ""
        self.menu_now="auto_mode"
        self.camera_perspective = "camera-top"
        self.helio_get_conn = ""
        self.helio_get_id = ""
        self.list_data_helio = []
        self.json_path_data = []
        self.is_path_found = False


    def apply_crop_methods(self, frame):

        with open('./data/setting/setting.json', 'r') as file:
            setting_data = json.load(file)

        if self.camera_perspective == "camera-bottom":
            M_bottom = np.array(setting_data['perspective_transform'])
            max_width_bottom = setting_data['max_width']
            max_height_bottom = setting_data['max_height']
            warped_top = cv2.warpPerspective(frame, M_bottom, (max_width_bottom, max_height_bottom))

            return warped_top, max_width_bottom, max_height_bottom
        
        elif self.camera_perspective == "camera-top":
            M_top = np.array(setting_data['perspective_transform_bottom'])
            max_width_top = setting_data['max_width_bottom']
            max_height_top = setting_data['max_height_bottom']
            warped_top = cv2.warpPerspective(frame, M_top, (max_width_top, max_height_top))

            return warped_top, max_width_top, max_height_top
        
    
    def find_bounding_boxes(self, gray_frame, blur_kernel, thresh_val, morph_kernel_size):
        blurred = cv2.GaussianBlur(gray_frame, blur_kernel, 0)
        _, thresh = cv2.threshold(blurred, thresh_val[0], thresh_val[1], cv2.THRESH_BINARY)
        kernel = np.ones(morph_kernel_size, np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        return contours, thresh


    def __find_bounding_boxes_hsv_mode(self, frame_color, low_H, low_S, low_V, high_H, high_S, high_V, blur_kernel):
        
        frame_HSV = cv2.cvtColor(frame_color, cv2.COLOR_BGR2HSV)
        blurred = cv2.GaussianBlur(frame_HSV, blur_kernel, 0)
        frame_threshold = cv2.inRange(blurred, (low_H, low_S, low_V), (high_H, high_S, high_V))
        kernel_morph = np.ones((7,7), np.uint8)
        frame_morph = cv2.morphologyEx(frame_threshold, cv2.MORPH_OPEN, kernel_morph)
        contours_light, _ = cv2.findContours(
            frame_morph, 
            cv2.RETR_TREE, 
            cv2.CHAIN_APPROX_NONE
        )
        
        return contours_light, frame_threshold
    
    def calculate_centers(self, contours):
        ###Calculate the centers of the given contours.###
        centers = []
        for cnt in contours:
            M = cv2.moments(cnt)
            if M['m00'] != 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
                centers.append((cx, cy))
        if not centers:
            return [], []
        center_x, center_y = zip(*centers)
        return list(center_x), list(center_y)
    
    def __calulate_centers_frame(self, frame):
        h, w = frame.shape[:2]
        center_x = w // 2
        center_y = h // 2
        center = (center_x, center_y)
        return center

    def call_open_camera(self):
        ###Initialize video capture and start updating frames.###
        try:
            if self.camera_connection != "" and self.helio_get_conn != "":
                if self.camera_connection != "":
                    if not self.capture:
                        try:
                            self.capture = cv2.VideoCapture(self.camera_connection, cv2.CAP_FFMPEG)
                            if not self.capture.isOpened():
                                self.show_popup("Error", "Could not open camera.")
                                self.ids.auto_camera_status.text = "Error: Could not open camera"
                                return
                            Clock.schedule_interval(self.update_frame, 1.0 / 30.0)  # 30 FPS
                            self.ids.auto_camera_status.text = "Auto menu || Camera status:On"
                        except Exception as e:
                            self.show_popup("Camera error", f"{e}")
            else:
                self.show_popup("Alert", "Camera or helio stats must not empty.")
        except Exception as e:
            print(e)

    def update_frame(self, dt):
        if self.capture:
            # try:
                ret, frame = self.capture.read()
                
                if not ret or frame is None:
                    print(frame)
                    return
                else:
                    frame = cv2.flip(frame, 0) ### <= flip
                    # print(frame)
                    frame, _, _ = self.apply_crop_methods(frame) 
                    ### frame bottom ###
                    contours_light, _ = self.__find_bounding_boxes_hsv_mode(
                            frame_color=frame, 
                            low_H=self.static_low_h, 
                            low_S=self.static_low_s, 
                            low_V=self.static_low_v,
                            high_H=self.static_high_h,
                            high_S=self.static_high_s,
                            high_V=self.static_high_v,
                            blur_kernel=self.static_blur_kernel
                        )

                        # Calculate centers
                    centers_light = self.calculate_centers(contours_light)
                    centers_frame = self.__calulate_centers_frame(frame)
                        
                    for cnt in contours_light:
                        c_area = cv2.contourArea(cnt)
                        if self.static_min_area < c_area: #and self.static_max_area > c_area:
                            x, y, w, h = cv2.boundingRect(cnt)
                            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                            cv2.circle(frame, (centers_light[0][0], centers_light[1][0]), 5, (255, 0, 0), -1)
                            cv2.putText(frame, "C-L", (centers_light[0][0], centers_light[1][0]+30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

                    ### draw center of frame
                    cv2.circle(frame, centers_frame, 5,  (0, 255, 0), -1)
                    cv2.putText(frame, "C-F", centers_frame, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        
                    # Convert frame to Kivy texture
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    texture_rgb = Texture.create(size=(frame_rgb.shape[1], frame_rgb.shape[0]), colorfmt='rgb')
                    texture_rgb.blit_buffer(frame_rgb.tobytes(), colorfmt='rgb', bufferfmt='ubyte')
                    self.ids.monitoring_frame.texture = texture_rgb
            # except Exception as e:
            #     print(f"Video stream file damage pass frame... => {e}")


    def show_popup(self, title, message):
        ### Display a popup with a given title and message. ###
        popup = Popup(title=title,
                    content=Label(text=message),
                    size_hint=(None, None), size=(400, 200))
        popup.open()

    def call_close_camera(self):
        try:
            if self.capture:
                self.capture.release()
                self.capture = None
                Clock.unschedule(self.update_frame)
                if hasattr(self, 'capture'):
                    self.cam_thread.stop()
                image_standby_path = "./images/sample_image_2.png"
                core_image = CoreImage(image_standby_path).texture
                self.ids.auto_cam_image.texture = core_image
                self.ids.auto_cam_image_demo.texture = core_image
                self.ids.auto_camera_status.text = "Manual menu || camera status off"
        except:
            pass

    def fetch_all_helio_cam(self):
        list_helio = []
        with open('./data/setting/connection.json', 'r') as file:
            data = json.load(file)
        self.list_data_helio = data['helio_stats_ip']
        # self.list_data_cam = data['camera_url']
        for item in data['helio_stats_ip']:
            if item['id'] != "all":
                list_helio.append(item['id'])
                
        self.ids.spinner_helio_selection.values = list_helio
        # self.ids.spinner_helio_selection.values = [item['id'] for item in data.get('helio_stats_ip', [])]

    def select_drop_down_menu_helio_path(self, spinner, text):
        for h_data in self.list_data_helio:
            if text == h_data['id']:
                self.helio_endpoint = "http://"+h_data['ip']+"/update-data"
                self.helio_get_conn = h_data['ip']
                self.helio_get_id = h_data['id']

    def haddle_change_hsv_threshold(self, value):
        try:
            self.static_low_v = value
            with open('./data/setting/setting.json', 'r') as file:
                setting_data = json.load(file)
            setting_data['hsv_threshold']['low_v'] = int(value)
            with open("./data/setting/setting.json", "w") as file:
                json.dump(setting_data, file, indent=4)
        except Exception as e:
            self.show_popup("Error", f"Failed to upload value in setting file: {e}")

    def haddle_reset_default_threshold_low_v(self):
        with open('./data/setting/setting.json', 'r') as file:
            setting_data = json.load(file)
        
        setting_data['hsv_threshold']['low_v'] = 180 ## default low_v

        with open("./data/setting/setting.json", "w") as file:
            json.dump(setting_data, file, indent=4)
        
        self.ids.slider_hsv_low_v.value = setting_data['hsv_threshold']['low_v']

    def haddle_start_get_data(self):
        Clock.schedule_interval(self.fetch_data_helio_stats, 5)

    def haddle_off_get_data(self):
        try:
            Clock.unschedule(self.fetch_data_helio_stats)
        except:
            pass

    def fetch_data_helio_stats(self, dt):
        # print("loop on")
        if self.helio_get_conn == "":
            self.show_popup("Alert", "Please select heliostats.")
        elif self.helio_get_conn == "all":
            self.show_popup("Alert", "Cannot select all heliostats.")
        else:
            try:  
                data = requests.get("http://"+self.helio_get_conn+"/",timeout=3)
                # data = requests.get("http://"+"192.168.0.106"+"/")
                # data = requests.get(url="http://192.168.0.106/")
                setJson = data.json()
                # print(setJson)
                # self.ids.val_id.text = str(setJson['id'])
                self.ids.val_current_x.text = str(setJson['currentX'])
                self.ids.val_current_y.text = str(setJson['currentY'])
                # self.ids.val_err_posx.text = str(setJson['err_posx'])
                # self.ids.val_err_posy.text = str(setJson['err_posy'])
                self.ids.val_label_x.text= str(setJson['safety']['x'])
                self.ids.val_label_y.text= str(setJson['safety']['y'])
                # self.ids.val_x1.text= str(setJson['safety']['x1'])
                # self.ids.val_y1.text= str(setJson['safety']['y1'])
                # self.ids.val_sl_1.text= str(setJson['safety']['ls1'])
                self.ids.val_st_path.text= str(setJson['safety']['st_path'])
                # self.ids.val_move_comp.text= str(setJson['safety']['move_comp'])
                self.ids.val_elevation.text= str(setJson['elevation'])
                self.ids.val_azimuth.text= str(setJson['azimuth'])
            except Exception as e:
                print(f"error connection {e}")
                self.show_popup("Alert", "connection error close get data.")
                self.haddle_off_get_data()

    def parse_text_file_to_json(self,file_path):
        data_list = []
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('*'):
                    json_str = line[1:]  
                    data = json.loads(json_str)
                    data_list.append(data)
        return data_list

    def haddle_monitor(self):
        dt = datetime.now()
        status_moni = self.ids.monitoring_helostats_data.text
        if self.helio_get_conn == "":
            self.show_popup("Alert", "Please select heliostats.")
        elif self.helio_get_conn == "all":
            self.show_popup("Alert", "Cannot select all heliostats.")
        # elif day == "" and month == "":
        #     self.show_popup("Alert", "To start monitor select date that path will use.")
        else: 
            if status_moni == "Start monitoring":
                directory = './model/forecasting'
                prefix = f"data_{self.helio_get_id}_{dt.day:02}{dt.month:02}"
                print(prefix)
                for filename in os.listdir(directory):
                    if filename.startswith(prefix) and filename.endswith('.txt'):
                        file_path = os.path.join(directory, filename)
                        # print(f"Found file: {file_path}")
                        # with open(file_path, 'r') as f:
                        #     content = f.read()
                        self.json_path_data = self.parse_text_file_to_json(file_path) 
                        self.is_path_found = True
                            
                if self.is_path_found == True:
                    self.ids.monitoring_helostats_data.text = "Off monitoring"
                    # self.haddle_start_get_data()
                    self.monitor_interval(dt)
                    self.start_monitor_interval()
                else:
                    self.show_popup("File not found.", f"Path not found check in ./model/forecasting/{prefix}")
                    self.ids.val_status_path_found.text = f"Path not found"
            else:
                self.ids.monitoring_helostats_data.text = "Start monitoring"
                # self.haddle_off_get_data()
                self.haddle_off_monitor()


    def haddle_off_monitor(self):
        Clock.unschedule(self.monitor_interval)
        self.ids.val_status_path_found.text = "Stop"
        self.ids.val_is_timing_x.text = "00:00:00"
        self.ids.val_predict_X.text = "null"
        self.ids.val_predict_y.text = "null"

    def start_monitor_interval(self):
        Clock.schedule_interval(self.monitor_interval, 10)

    def monitor_interval(self, dt):
        dt = datetime.now()
        time_for_show = dt.strftime('%H:%M:%S')
        time_str = dt.strftime('%H:%M')
        for item in self.json_path_data:
            t = datetime.strptime(item['timestamp'], '%H:%M:%S')
            time_str_path = t.strftime('%H:%M')
            if time_str == time_str_path:
                self.ids.val_status_path_found.text = "Found path"
                self.ids.val_is_timing_x.text = time_for_show
                self.ids.val_predict_X.text = str(item['x'])
                self.ids.val_predict_y.text = str(item['y'])

    def haddle_off_get_data(self):
        pass

    def stop_fetch_loop(self):
        pass