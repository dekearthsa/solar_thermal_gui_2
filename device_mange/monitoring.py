import json
import cv2
import numpy as np
from kivy.clock import Clock
# from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.graphics.texture import Texture
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.core.image import Image as CoreImage
# from kivy.uix.boxlayout import BoxLayout
# from kivy.uix.button import Button
# from kivy.uix.textinput import TextInput
# from kivy.uix.gridlayout import GridLayout
# from camera_control.handle_thread_cpu import CameraThread
# from functools import partial

class Monitoring(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        ### mqtt setup ###
        self.capture = None
        self.selected_points = []      # List to store selected points as (x, y) in image coordinates
        self.polygon_lines = None      # Line instruction for the polygon
        self.point_markers = []        # Ellipse instructions for points
        self.crop_area = None          # To store the crop area coordinates (if using rectangle)

        self.perspective_transform = [[0,0,0], [0,0,0],[0,0,0]]
        self.max_width = 0
        self.max_height = 0
        
        self.reset_perspective_transform = [[0,0,0], [0,0,0],[0,0,0]]
        self.reset_max_width = 0
        self.reset_max_height = 0

        # Clock.schedule_once(lambda dt: self.fetch_status()) # Fetch status is_use_contour from json setting file
        self.dragging = False          # Initialize dragging
        self.rect = None               # Initialize rectangle
        self.status_text = 'Ready'     # Initialize status text
        Clock.schedule_once(lambda dt: self.fetch_all_helio_cam())
        # Clock.schedule_once(lambda dt: self.fetch_helio_stats_data())
        # Clock.schedule_once(lambda dt: self.haddle_fetch_threshold_data())
        # Clock.schedule_interval(lambda dt: self.fetch_storage_endpoint(),2)
        

        #### IN DEBUG MODE CHANGE THRES HERE ####
        self.static_low_h = 0 #10
        self.static_low_s = 0
        self.static_low_v = 180
        self.static_high_h = 179
        self.static_high_s = 255
        self.static_high_v = 255
        self.static_blur_kernel = (55,55) 
        self.static_min_area = 50000
        self.static_max_area = 130000 
        self.camera_connection = ""
        self.helio_stats_connection = ""
        self.menu_now="auto_mode"
        self.camera_perspective = ""


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
        
    # def fetch_status(self):
    #     ###Fetch settings from JSON and update UI accordingly.###
    #     try:
    #         with open('./data/setting/setting.json', 'r') as file:
    #             setting_data = json.load(file)
    #     except Exception as e:
    #         self.show_popup("Error", f"Failed to load settings: {e}")
    #         return

        # # Update the status label based on 'is_use_contour'
        # if not setting_data.get('is_use_contour', False):
        #     self.ids.using_crop_value_status.text = "Using Crop: Off"
        # else:
        #     self.ids.using_crop_value_status.text = "Using Crop: On"
 
    def remove_draw_point_marker(self):
        # Clear point markers
        img_widget = self.ids.auto_cam_image
        for marker in self.point_markers:
            img_widget.canvas.after.remove(marker)
        self.point_markers = []

        # Remove polygon lines
        if self.polygon_lines:
            img_widget.canvas.after.remove(self.polygon_lines)
            self.polygon_lines = None

    def reset_selection(self):
        ###Reset the selected points and clear drawings.###
        self.selected_points = []
        self.status_text = 'Selection reset. Select points by clicking on the image.'

        # Clear point markers
        img_widget = self.ids.auto_cam_image
        for marker in self.point_markers:
            img_widget.canvas.after.remove(marker)
        self.point_markers = []

        # Remove polygon lines
        if self.polygon_lines:
            img_widget.canvas.after.remove(self.polygon_lines)
            self.polygon_lines = None

        # Clear rectangle if in rectangle mode
        if hasattr(self, 'rect') and self.rect:
            img_widget.canvas.after.remove(self.rect)
            self.rect = None

    
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
            with open('./data/setting/setting.json') as file:
                setting_json = json.load(file)
            if setting_json['crop_status'] == True:
                if setting_json['is_run_path'] != 1:
                    if self.camera_connection != "" and self.helio_stats_connection != "":
                        if self.camera_connection != "":
                            if not self.capture:
                                try:
                                    self.capture = cv2.VideoCapture(self.camera_connection, cv2.CAP_FFMPEG)
                                    self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1) ## new setup 

                                    if not self.capture.isOpened():
                                        self.show_popup("Error", "Could not open camera.")
                                        self.ids.auto_camera_status.text = "Error: Could not open camera"
                                        return
                                    # self.capture = CameraThread(0)
                                    Clock.schedule_interval(self.update_frame, 1.0 / 30.0)  # 30 FPS
                                    self.ids.auto_camera_status.text = "Auto menu || Camera status:On"
                                except Exception as e:
                                    self.show_popup("Camera error", f"{e}")
                    else:
                        self.show_popup("Alert", "Camera or helio stats must not empty.")
                else:
                    self.show_popup("Alert", "Path system is running\n Stop path system to run auto")
            else:
                self.show_popup("Alert", "Camera not setting.")
        except Exception as e:
            print(e)

    def update_frame(self, dt):
        # self.capture.start()
        # if not hasattr(self, 'capture'):
        #     return 
                
        # ret, frame = self.capture.read()
        if self.capture:
            try:
                # ret, frame = self.capture.read()
                # if not hasattr(self, 'capture'):
                #     return 
                
                ret, frame = self.capture.read()
                
                if not ret or frame is None:
                    print(frame)
                    return
                else:
                        frame = cv2.flip(frame, 0) ### <= flip
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
                        # texture_bin = Texture.create(size=(bin_light.shape[1], bin_light.shape[0]), colorfmt='luminance')
                        # texture_bin.blit_buffer(bin_light.tobytes(), colorfmt='luminance', bufferfmt='ubyte')

                        self.ids.monitoring_frame.texture = texture_rgb
                        # self.ids.auto_cam_image_demo.texture = texture_bin


                    
            except Exception as e:
                print("Video stream file damage pass frame...")


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

    def fetch_helio_stats_data(self):
        # with open('./data/setting/connection.json', 'r') as file:
        #     data = json.load(file)
        with open('./data/setting/setting.json', 'r') as setting_file:
            setting_json = json.load(setting_file)
        # self.ids.spinner_helio_stats.values = [item['id'] for item in data.get('helio_stats_ip', [])]
        # self.ids.spinner_camera.values = [item['id'] for item in data.get('camera_url', [])]
        self.camera_perspective = setting_json['storage_endpoint']['camera_ip']['id']

    def select_drop_down_menu_camera(self,spinner, text):
        # self.call_close_camera()
        # self.show_popup("Alert", "Camera change")
        
        self.ids.selected_label_camera.text = f"ID: {text}"
        self.camera_perspective = text
        # print("text =>" , text)
        try:
            with open('./data/setting/connection.json', 'r') as file:
                storage = json.load(file)
            
            if self.camera_connection == "":
                for camera_name in storage['camera_url']:
                    if text == camera_name['id']:
                        self.camera_connection =  camera_name['url']

            with open('./data/setting/setting.json', 'r') as file:
                storage = json.load(file)

            storage['storage_endpoint']['camera_ip']['ip'] = self.camera_connection
            storage['storage_endpoint']['camera_ip']['id'] = text

            with open('./data/setting/setting.json', 'w') as file:
                json.dump(storage, file, indent=4)
            
        except Exception as e:
            self.show_popup("Error", f"{e}")

    def fetch_all_helio_cam(self):
        with open('./data/setting/connection.json', 'r') as file:
            data = json.load(file)
        self.list_data_helio = data['helio_stats_ip']
        self.list_data_cam = data['camera_url']
        self.ids.spinner_helio_selection.values = [item['id'] for item in data.get('helio_stats_ip', [])]

    def select_drop_down_menu_helio_path(self, spinner, text):
        for h_data in self.list_data_helio:
            if text == h_data['id']:
                self.helio_endpoint = "http://"+h_data['ip']+"/update-data"
                self.helio_get_data = h_data['ip']


    # def fetch_storage_endpoint(self):
    #     with open('./data/setting/setting.json', 'r') as file:
    #         setting_data = json.load(file) 
        
    #     self.ids.selected_label_helio_stats.text = setting_data['storage_endpoint']['helio_stats_ip']['id']
    #     self.ids.selected_label_camera.text = setting_data['storage_endpoint']['camera_ip']['id']
    #     self.camera_connection =  setting_data['storage_endpoint']['camera_ip']['ip']
    #     self.helio_stats_connection = setting_data['storage_endpoint']['helio_stats_ip']['ip']

    def haddle_off_get_data(self):
        pass

    def stop_fetch_loop(self):
        pass