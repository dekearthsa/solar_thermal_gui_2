import os
import json
import logging
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
import tensorflow as tf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import math
import pytz
from pysolar.solar import get_altitude, get_azimuth
from pysolar.radiation import get_radiation_direct
import json
from kivy.clock import Clock

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
logging.getLogger('tensorflow').setLevel(logging.ERROR)

class Forecasting(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(lambda dt: self.fetch_all_helio_cam())
        self.list_heliostats_id = ['h1','h2','h3','h4','h5','h6','h7','h6','h9','h10','h11','h12']
        self.helio_get_id = ""
    def haddle_off_get_data(self):
        pass

    def call_close_camera(self):
        pass

    def stop_fetch_loop(self):
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

    def select_drop_down_menu_helio_path(self, spinner, text):
        for h_data in self.list_data_helio:
            if text == h_data['id']:
                self.helio_get_id = h_data['id']

    def get_solar_declination(self,date: datetime) -> float:
        n  = date.timetuple().tm_yday
        return -23.44 * math.cos(math.radians(360 / 365 * (n + 10)))

    def get_solar_hour_angle(self,date: datetime, lon: float) -> float:
        n  = date.timetuple().tm_yday
        B  = math.radians((360 / 365) * (n - 81))
        eot = 9.87 * math.sin(2*B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)

        utc_time = date.astimezone(pytz.utc)
        utc_hour = utc_time.hour + utc_time.minute/60 + utc_time.second/3600
        lst      = utc_hour + lon / 15 + eot / 60
        return 15 * (lst - 12)

    def gen_time_range(self, tz, start_dt: datetime, end_dt: datetime, step_min: int = 1):
        minutes = int((end_dt - start_dt).total_seconds() // 60)
        return [start_dt + timedelta(minutes=i) for i in range(0, minutes+1, step_min)]

    def generate_data(self):
        current_time = datetime.now()
        TIME_ZONE = "Asia/Bangkok"
        LATITUDE = 14.382198
        LONGITUDE = 100.842897
    
        ANGLES = {
            "h1": (-6000,  8487, 1350),
            "h2": (-3000,  8487, 1350),
            "h3": (    0,  8487, 1350),
            "h4": ( 3000,  8487, 1350),
            "h5": ( 6000,  8487, 1350),
            "h6": (-4500, 11487, 1350),
            "h7": (-1500, 11487, 1350),
            "h8": ( 1500, 11487, 1350),
            "h9": ( 4500, 11487, 1350),
            "h10": ( -1500, 5987, 1350),
            "h11": ( 1500, 5987, 1350),
            "h12": ( 4500, 5987, 1350)
        }

        # TARGET_HELIO = self.ids.heliostats_id.text

        TARGET_HELIO = self.helio_get_id
        TARGET_HELIO = TARGET_HELIO.strip()
        TARGET_HELIO = TARGET_HELIO.lower()
        RECIVER_ANGLE = 45
        CALIBRATE_ANGLE = 58
        CAMERA = "top"

        start_time = self.ids.time_start.text
        end_time = self.ids.time_end.text

        DAY = self.ids.is_day_predict.text
        MONTH = self.ids.is_month_predict.text
        YEAR = self.ids.is_year_predict.text

        if  DAY == "" and MONTH == "" and YEAR == "": 
            self.show_confirm(title="Missing input",message=f"Save missing input!")
        elif TARGET_HELIO not in self.list_heliostats_id:
            self.show_confirm(title="Invalid heliostats id",message=f"Heliostats {TARGET_HELIO} not in list.")
        else:
            start_time = int(start_time)
            end_time = int(end_time)
            DAY = int(DAY)
            MONTH = int(MONTH)
            YEAR = int(YEAR)

            PLUS_NEXT_DAY = (int(current_time.day) - DAY)
            FILENAME= f"data_{TARGET_HELIO}_{DAY:02}{MONTH:02}.txt"
            tz   = pytz.timezone(TIME_ZONE)
            start_bkk = tz.localize(datetime(YEAR, MONTH, DAY, start_time, 0, 0)) + timedelta(days=PLUS_NEXT_DAY)
            end_bkk   = start_bkk.replace(hour=end_time, minute=0)

            times_bkk = self.gen_time_range(tz, start_bkk, end_bkk, step_min=1)
            x_angle, y_angle, z_angle = ANGLES[TARGET_HELIO]

            rows = []
            for t_bkk in times_bkk:
                t_utc  = t_bkk.astimezone(pytz.utc)
                altitude   = get_altitude (LATITUDE, LONGITUDE, t_utc)
                azimuth    = get_azimuth  (LATITUDE, LONGITUDE, t_utc)
                radiation  = get_radiation_direct(t_utc, LATITUDE)
                declination= self.get_solar_declination(t_bkk)
                hour_angle = self.get_solar_hour_angle(t_bkk, LONGITUDE)

                rows.append({
                    "heliostats_id": TARGET_HELIO,
                    "x_angle": x_angle,
                    "y_angle": y_angle,
                    "z_angle": z_angle,
                    "timestamp": t_bkk.isoformat(),
                    "string_date": t_bkk.strftime("%d/%m/%y %H:%M:%S"),
                    "is_day":   t_bkk.day,
                    "is_month": t_bkk.month,
                    "is_year":  t_bkk.year % 100,
                    "is_lat": float(round(LATITUDE, 5)),
                    "is_lng": float(round(LONGITUDE, 5)),
                    "altitude":   float(round(altitude,   5)),
                    "azimuth":    float(round(azimuth,    5)),
                    "declination": float(round(declination,5)),
                    "hour_angle": float(round(hour_angle, 5)),
                    "radiation":  float(round(radiation,  5)),
                    "reciver_angle":   RECIVER_ANGLE,
                    "calibrate_angle": CALIBRATE_ANGLE,
                    "camera": CAMERA,
                })

            json_str = json.dumps(rows)
            df_main = pd.read_json(json_str) 
            df_camera_dummies = pd.get_dummies(df_main['camera'])
            df_main['camera_top'] = df_camera_dummies['top']
            df_main['camera_bottom'] =  False

            df_main['datetime'] = pd.to_datetime(df_main['string_date'], format='%d/%m/%y %H:%M:%S')

            df_main['timestamp'] = df_main['datetime'].astype('int64') // 1e9  # convert to seconds

            df_main['year'] = df_main['datetime'].dt.year
            df_main['month'] = df_main['datetime'].dt.month
            df_main['day'] = df_main['datetime'].dt.day
            df_main['hour'] = df_main['datetime'].dt.hour
            df_main['minute'] = df_main['datetime'].dt.minute
            df_main['second'] = df_main['datetime'].dt.second
            df_main['dayofyear'] = df_main['datetime'].dt.dayofyear
            df_main['weekofyear'] = df_main['datetime'].dt.isocalendar().week  #

            df_main = df_main.drop(columns=['string_date'])
            df_main = df_main.drop(columns=['camera'])
            df_main['camera_bottom'] = df_main['camera_bottom'].astype(int)
            df_main['camera_top'] = df_main['camera_top'].astype(int)
            df_main['weekofyear'] = df_main['datetime'].dt.isocalendar().week.astype(int)
            df_main = df_main.drop(columns=['datetime'])
            get_only_date = df_main[['hour','minute','second']]
            np_df = df_main.drop(columns = ['timestamp', 'second','is_day', 'is_month', 'is_year' ])

            new_order = [
                "x_angle",
                "y_angle",
                "z_angle",
                "altitude",
                "azimuth",
                "declination",
                "hour_angle",
                "radiation",
                "month",
                "day",
                "hour",
                "minute",
                "dayofyear",
                "weekofyear",
            ]
            np_df = np_df[new_order]
            df_22_np_array = np.array(np_df)    

            model =  tf.keras.models.load_model('/Users/pcsishun/project_solar_thermal/gui_solar_thermal/model/model.keras')
            result_current_22 = model.predict(df_22_np_array)
            arr_rounded = np.round(result_current_22, 2)
            np_df['x'] = arr_rounded[:,0]
            np_df['y'] = arr_rounded[:, 1]

            df_predict = pd.DataFrame(arr_rounded, columns=['x', 'y'])
            df_predict['timestamp'] = get_only_date.apply(lambda row: f"{int(row['hour']):02}:{int(row['minute']):02}:{int(row['second']):02}", axis=1)
            save_dir = '/Users/pcsishun/project_solar_thermal/gui_solar_thermal/model/forecasting'
            filepath = os.path.join(save_dir, FILENAME)
            with open(filepath, "w") as f:
                for _, row in df_predict.iterrows():
                    line = f'*{{"timestamp": "{row["timestamp"]}", "x": {row["x"]:.2f}, "y": {row["y"]:.2f}}}\n'
                    f.write(line)
            self.show_confirm(title="Predict success" ,message=f"Save success at {filepath}")
            print(f"✔ File saved to: {filepath}")

    def enforce_range(self, instance, min_value, max_value):
        text = instance.text
        if text.isdigit():
            val = int(text)
            if val > max_value:
                instance.text = str(max_value)
            elif val < min_value:
                instance.text = str(min_value)

    def show_confirm(self,title, message):
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