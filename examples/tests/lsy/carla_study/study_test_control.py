
from __future__ import print_function

# ==============================================================================
# -- find carla module ---------------------------------------------------------
# ==============================================================================


import glob
import os
import sys
from csv_coordinate.repository.CsvCoordinateRepositoryImpl import CsvCoordinateRepositoryImpl
import time
import csv

# from reportlab.lib.colors import cyan, red, green, white, orange


try:
    sys.path.append(
        glob.glob(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/carla/dist/carla-*%d.%d-%s.egg' % (
            sys.version_info.major,
            sys.version_info.minor,
            'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

# ==============================================================================
# -- imports -------------------------------------------------------------------
# ==============================================================================


import carla

from carla import ColorConverter as cc
# import PythonAPI
# import PythonAPI.util

# from carla import draw_waypoint_union, draw_transform
# from lane_explorer import draw_waypoint_union, draw_transform, cyan, red, green, white, orange
import argparse
import collections
import datetime
import logging
import math
import random
import re
import weakref

try:
    import pygame
    from pygame.locals import KMOD_CTRL
    from pygame.locals import KMOD_SHIFT
    from pygame.locals import K_0
    from pygame.locals import K_9
    from pygame.locals import K_BACKQUOTE
    from pygame.locals import K_BACKSPACE
    from pygame.locals import K_COMMA
    from pygame.locals import K_DOWN
    from pygame.locals import K_ESCAPE
    from pygame.locals import K_F1
    from pygame.locals import K_LEFT
    from pygame.locals import K_PERIOD
    from pygame.locals import K_RIGHT
    from pygame.locals import K_SLASH
    from pygame.locals import K_SPACE
    from pygame.locals import K_TAB
    from pygame.locals import K_UP
    from pygame.locals import K_a
    from pygame.locals import K_b
    from pygame.locals import K_c
    from pygame.locals import K_d
    from pygame.locals import K_g
    from pygame.locals import K_h
    from pygame.locals import K_i
    from pygame.locals import K_l
    from pygame.locals import K_m
    from pygame.locals import K_n
    from pygame.locals import K_p
    from pygame.locals import K_k
    from pygame.locals import K_j
    from pygame.locals import K_q
    from pygame.locals import K_r
    from pygame.locals import K_s
    from pygame.locals import K_v
    from pygame.locals import K_w
    from pygame.locals import K_x
    from pygame.locals import K_z
    from pygame.locals import K_MINUS
    from pygame.locals import K_EQUALS
except ImportError:
    raise RuntimeError('cannot import pygame, make sure pygame package is installed')

try:
    import numpy as np
except ImportError:
    raise RuntimeError('cannot import numpy, make sure numpy package is installed')

red = carla.Color(255, 0, 0)
green = carla.Color(0, 255, 0)
blue = carla.Color(47, 210, 231)
cyan = carla.Color(0, 255, 255)
yellow = carla.Color(255, 255, 0)
orange = carla.Color(255, 162, 0)
white = carla.Color(255, 255, 255)

trail_life_time = 10
waypoint_separation = 10


# ==============================================================================
# -- Global functions ----------------------------------------------------------
# ==============================================================================


    # 디버깅 목적으로 사용되는 화살표를 그리는 함수
    # 주어진 변환(trans)에 따라 화살표를 그림
    # 화살표는 변환의 위치(trans.location)에서 변환의 전진 벡터(trans.get_forward_vector())로 향하는 방향을 나타냄
def draw_transform(debug, trans, col=carla.Color(255, 0, 0), lt=-1):
    # debug: 디버깅 도구를 나타내는 carla.DebugHelper 객체
    # trans: 변환 정보를 담고 있는 carla.TransForm 객체
    # col: 화살표의 색상을 나태내는 carla.Color 객체
    # lt: 화살표의 생명 주기를 나타내는 숫자 기본값은 -1로, 영구적으로 유지되도록 함
    debug.draw_arrow(
        trans.location, trans.location + trans.get_forward_vector(),
        thickness=0.05, arrow_size=0.1, color=col, life_time=lt)


# 두 개의 웨이포인트 사이에 선을 그리고, 두 번째 웨이포인트에 점을 그리는 함수
# 웨이포인트는 3D 방향성 점으로, 도로에서의 위치와 차선에 따른 방향을 저장
# 디버깅 목적으로 사용되며, 선과 점의 색상, 생명 주기, 그리고 선이 지속적으로 유지되는지 여부를 설정할 수 있음
def draw_waypoint_union(debug, w0, w1, color=carla.Color(255, 0, 0), lt=5):
    debug.draw_line(
        w0.transform.location + carla.Location(z=0.25),
        w1.transform.location + carla.Location(z=0.25),
        thickness=0.1, color=color, life_time=lt, persistent_lines=False)
    debug.draw_point(w1.transform.location + carla.Location(z=0.25), 0.1, color, lt, False)


# 웨이포인트에 대한 정보를 그래픽으로 표시하는 기능
def draw_waypoint_info(debug, w, lt=5):
    # w_loc 에는 웨이포인트의 위치 정보가 저장
    w_loc = w.transform.location
    # debug.draw_string 메서드를 사용하여 웨이포인트의 위치에 다음 정보를 표시
    # 차선 id 를 포함하는 문자열을 노란색으로 표시
    # 도로 id 를 포함하는 문자열을 파란색으로 표시
    # 차선 변경 상태를 포함하는 문자열을 빨간색으로 표시
    # 각 텍스트는 웨이포인트의 위치에 상대적으로 다른 z 좌표에 배치
    # lt 인자는 텍스트가 화면에 얼마나오래 표시될지를 결정
    debug.draw_string(w_loc + carla.Location(z=0.5), "lane: " + str(w.lane_id), False, yellow, lt)
    debug.draw_string(w_loc + carla.Location(z=1.0), "road: " + str(w.road_id), False, blue, lt)
    debug.draw_string(w_loc + carla.Location(z=-.5), str(w.lane_change), False, red, lt)


# 교차로의 경계 상자와 각 차선의 초기 및 최종 거점을 그리는 함수
def draw_junction(debug, junction, l_time=10):
    """Draws a junction bounding box and the initial and final waypoint of every lane."""
    # draw bounding box
    box = junction.bounding_box
    point1 = box.location + carla.Location(x=box.extent.x, y=box.extent.y, z=2)
    point2 = box.location + carla.Location(x=-box.extent.x, y=box.extent.y, z=2)
    point3 = box.location + carla.Location(x=-box.extent.x, y=-box.extent.y, z=2)
    point4 = box.location + carla.Location(x=box.extent.x, y=-box.extent.y, z=2)
    debug.draw_line(
        point1, point2,
        thickness=0.1, color=orange, life_time=l_time, persistent_lines=False)
    debug.draw_line(
        point2, point3,
        thickness=0.1, color=orange, life_time=l_time, persistent_lines=False)
    debug.draw_line(
        point3, point4,
        thickness=0.1, color=orange, life_time=l_time, persistent_lines=False)
    debug.draw_line(
        point4, point1,
        thickness=0.1, color=orange, life_time=l_time, persistent_lines=False)
    # draw junction pairs (begin-end) of every lane
    junction_w = junction.get_waypoints(carla.LaneType.Any)
    for pair_w in junction_w:
        # draw_transform 함수를 사용하여 각 거점의 위치를 시각적으로 표시
        draw_transform(debug, pair_w[0].transform, orange, l_time)
        # draw_point 와 draw_line 메서드를 사용하여 거점과 선을 그림
        debug.draw_point(
            pair_w[0].transform.location + carla.Location(z=0.75), 0.1, orange, l_time, False)
        draw_transform(debug, pair_w[1].transform, orange, l_time)
        debug.draw_point(
            pair_w[1].transform.location + carla.Location(z=0.75), 0.1, orange, l_time, False)
        debug.draw_line(
            pair_w[0].transform.location + carla.Location(z=0.75),
            pair_w[1].transform.location + carla.Location(z=0.75), 0.1, white, l_time, False)


# 날씨 프리셋을 찾는 함수
def find_weather_presets():
    rgx = re.compile('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)')
    name = lambda x: ' '.join(m.group(0) for m in rgx.finditer(x))
    # 클래스의 모든 속성을 찾아 대문자로 시작하는 속성만 선택
    presets = [x for x in dir(carla.WeatherParameters) if re.match('[A-Z].+', x)]
    return [(getattr(carla.WeatherParameters, x), name(x)) for x in presets]


# actor 이름을 가져와서 특정 길이로 잘라내는 기능. 첫 번째 단어를 제외한 나머지 단어들을 대문자로 변환한 후, 이를 합쳐서 배우의 표시 이름을 만듬
# 만약 주어진 길이보다 길다면, 이름을 잘라내고 끝에 줄임표를 붙여서 반환. 그렇지 않다면, 이름을 그대로 반환
def get_actor_display_name(actor, truncate=250):
    name = ' '.join(actor.type_id.replace('_', '.').title().split('.')[1:])
    return (name[:truncate - 1] + u'\u2026') if len(name) > truncate else name


# ==============================================================================
# -- World ---------------------------------------------------------------------
# ==============================================================================


# 이 클래스는 CARLA 시뮬레이터에서 사용되는 다양한 센서와 맵 정보, 날씨 설정 등을 관리하고,
# 시뮬레이션 상태를 업데이트하는 역할
# 각 센서와 맵 레이어는 시뮬레이션 내에서 다양한 정보를 제공하거나 시뮬레이션의 시각적 표현을 담당
class World(object):
    def __init__(self, carla_world, hud, args):
        self.world = carla_world # carla 시뮬레이터 워드 객체
        self.debug = carla.DebugHelper # carla 디버그 도구
        self.actor_role_name = args.rolename # 액터(자동차 등)의 역할 이름
        try:
            self.map = self.world.get_map() # 시뮬레이션 맵 정보 가져오기
        except RuntimeError as error:
            print('RuntimeError: {}'.format(error)) # 런타임 에러 메시지 출력
            print('  The server could not send the OpenDRIVE (.xodr) file:') # 서버가 OpenDRIVE 파일을 보낼 수 없음
            # 파일이 존재하고, 동일한 이름의 동네와 정확한지 확인
            print('  Make sure it exists, has the same name of your town, and is correct.')
            sys.exit(1) # 프로그램 종료
        self.hud = hud # 헤드업 디스플레이 객체
        self.player = None # 플레이어 객체
        self.collision_sensor = None # 충돌 센서 객체
        self.obstacle_sensor = None # 장애물 침범 센서 객체
        self.lane_invasion_sensor = None # 차선 침범 센서 객체
        self.gnss_sensor = None # GNSS 센서 객체
        self.imu_sensor = None # IMU 센서 객체
        self.radar_sensor = None # 레이더 센서 개체
        self.camera_manager = None # 카메라 관리자 객체
        self._weather_presets = find_weather_presets() # 날씨 설정 프리셋 찾기
        self._weather_index = 0 # 날씨 인덱스
        self._actor_filter = args.filter # 액터 필터
        self._gamma = args.gamma # 감마 값
        self.restart() # 시뮬레이션 재시작
        self.world.on_tick(hud.on_world_tick) # 시뮬레이션 틱마다 HUD 업데이트
        self.recording_enabled = False # 녹화 활성화 여부
        self.recording_start = 0 #  # 녹화 시작 시간
        self.constant_velocity_enabled = False # 일정 속도 활성화 여부
        self.current_map_layer = 0 # 현재 맵 레이어
        self.map_layer_names = [ # 맵 레이어 이름 리스트
            carla.MapLayer.NONE,
            carla.MapLayer.Buildings,
            carla.MapLayer.Decals,
            carla.MapLayer.Foliage,
            carla.MapLayer.Ground,
            carla.MapLayer.ParkedVehicles,
            carla.MapLayer.Particles,
            carla.MapLayer.Props,
            carla.MapLayer.StreetLights,
            carla.MapLayer.Walls,
            carla.MapLayer.All
        ]

# 플레이어 차량을 재시작하는 함수
    def restart(self):
        self.player_max_speed = 1.589
        self.player_max_speed_fast = 3.713
        # 카메라 관리자의 인덱스와 변환 인덱스를 저장
        # 카메라 관리자는 시뮬레이션 내에서 카메라의 위치와 방향을 관리하는 역할
        # 카메라 관리자가 이미 존재할 경우 그 인덱스와 변환 인덱스를 저장하고,
        # 그렇지 않을 경우 기본값인 0 을 사용
        # Keep same camera config if the camera manager exists.
        cam_index = self.camera_manager.index if self.camera_manager is not None else 0
        cam_pos_index = self.camera_manager.transform_index if self.camera_manager is not None else 0
        # Get a random blueprint.

        # CARLA 시뮬레이터의 블루프린트 라이브러리에서 'vehicle.carlamotors.carlacola' 필터를 사용하여 차량 블루프린트를 가져옴
        vehicle_blueprints = self.world.get_blueprint_library().filter('vehicle.carlamotors.carlacola')

        blueprint = vehicle_blueprints[0]

        # blueprint = random.choice(self.world.get_blueprint_library().filter(self._actor_filter))
        # blueprint.set_attribute('role_name', self.actor_role_name)

        # 선택된 블루프린트에 대해 여러 속성을 설정. 색상, 드라이버 ID, 무적상태 등의 속성을 랜덤으로 선택하여 설정
        # 치량의 외관과 동작을 변경하기 위한 것
        if blueprint.has_attribute('color'):
            color = random.choice(blueprint.get_attribute('color').recommended_values)
            blueprint.set_attribute('color', color)
        if blueprint.has_attribute('driver_id'):
            driver_id = random.choice(blueprint.get_attribute('driver_id').recommended_values)
            blueprint.set_attribute('driver_id', driver_id)
        if blueprint.has_attribute('is_invincible'):
            blueprint.set_attribute('is_invincible', 'true')

        # 블루프린트에 'speed' 속성이 있는 경우, 이 속성의 권장 값을 사용하여 플레이어의 최대 속도와 빠른 속도를 설정
        # set the max speed
        if blueprint.has_attribute('speed'):
            self.player_max_speed = float(blueprint.get_attribute('speed').recommended_values[1])
            self.player_max_speed_fast = float(blueprint.get_attribute('speed').recommended_values[2])
        else:
            print("No recommended values for 'speed' attribute")

        # 플레이어(자율 주행 차량)를 생성하고 배치하는 부분
        # Spawn the player.
        if self.player is not None:
            # 이전 플레이어의 위치 및 방향 정보를 가져옴
            spawn_point = self.player.get_transform()
            spawn_point.location.z += 2.0
            spawn_point.rotation.roll = 0.0
            spawn_point.rotation.pitch = 0.0
            # 이전 플레이어를 제거
            self.destroy()
            # 맵에서 가능한 스폰 포인트(플레이어를 배치할 수 있는 위치)를 가져옴
            spawn_points = self.map.get_spawn_points()
            # 가능한 스폰 포인트가 있다면 그 중에서 랜덤하게 선택하고, 없으면 기본값으로 carla.Transform()을 사용
            spawn_point = random.choice(spawn_points) if spawn_points else carla.Transform()
            # 선택된 스폰 포인트에 새로운 플레이어를 생성하고 배치
            self.player = self.world.try_spawn_actor(blueprint, spawn_point)
        while self.player is None:
            if not self.map.get_spawn_points():
                print('There are no spawn points available in your map/town.')
                print('Please add some Vehicle Spawn Point to your UE4 scene.')
                sys.exit(1)

            spawn_points = self.map.get_spawn_points()
            spawn_point = random.choice(spawn_points) if spawn_points else carla.Transform()
            self.player = self.world.try_spawn_actor(blueprint, spawn_point)

        # Set up the sensors.
        # 충돌 센서를 설정. self.hud 는 HUD(헤드업 디스플레이)를 가리킵니다. 이 센서는 충돌을 감지합니다.
        self.collision_sensor = CollisionSensor(self.player, self.hud)
        # 장애물 센서를 설정. 이 센서는 플레이어와 HUD를 인자로 받아들이며, 시야 내의 장애물을 감지
        self.obstacle_sensor = LineOfSightSensor(self.player, self.hud)
        # 차선 침범 센서를 설정. 플레이어와 HUD를 인자로 받아들이며, 차량이 차선을 침범하는지 감지
        self.lane_invasion_sensor = LaneInvasionSensor(self.player, self.hud)
        # GNSS(GPS) 센서를 설정. 이 센서는 플레이어를 추적하여 위치 정보를 제공
        self.gnss_sensor = GnssSensor(self.player)
        # IMU(Inertial Measurement Unit) 센서를 설정. 이 센서는 플레이어의 움직임을 추적하고 가속도, 각 가속도 등의 정보를 제공
        self.imu_sensor = IMUSensor(self.player)
        # 카메라 관리자를 설정. HUD 및 감마값을 인자로 받아들입니다. 이 카메라 관리자는 플레이어 주변의환경을 감시하는 카메라를 관리
        self.camera_manager = CameraManager(self.player, self.hud, self._gamma)
        # 카메라 관리자의 변환 인덱스를 이전에 저장된 값으로 설정. 이것은 카메라의 위치와 방향을 결정
        self.camera_manager.transform_index = cam_pos_index
        # 이전에 저장된 카메라 인덱스를 상ㅇ하여 카메라를 설정. 'notify=False'는 변경 사항을 알리지 않도록 설정
        self.camera_manager.set_sensor(cam_index, notify=False)
        # 플레이어의 유형을 가져옵니다. 이는 HUD를 통해 상ㅇ자에게 알림을 표시하는데 사용
        actor_type = get_actor_display_name(self.player)
        # HUD를 통해 플레이어의 유형에 대한 알림을 표시
        self.hud.notification(actor_type)

    # 다음 날씨를 설정하는 역할
    def next_weather(self, reverse=False):
        # 현재 날씨 인덱스를 업데이트 'reverse' 매개변수가 True 이면 이전 날씨를, 그렇지 않으면 다음 날씨를 선택
        self._weather_index += -1 if reverse else 1
        # 날씨 인덱스를 날씨 프리셋 리스트의 길이로 나눈 나머지를 구합니다. 이렇게 함으로써 인덱스가 날씨 프리셋 리스트의 범위를 벗어나지 않도록 합니다.
        self._weather_index %= len(self._weather_presets)
        # 현재 인덱스에 해당하는 날씨 프리셋을 가져옵니다.
        preset = self._weather_presets[self._weather_index]
        # HUD를 통해 상ㅇ자에게 선택된 날씨를 표시하는 알림을 보내니다. 여기서 %s 는 문자열 형식 지정자를 나타내며, 이를 통해 날씨 프리셋의 두번째 요소를 문자열로 변환하여 표시
        self.hud.notification('Weather: %s' % preset[1])
        # 플레이어가 속한 월드의 날씨를 설정 'preset[0]' 은 날씨 설정
        self.player.get_world().set_weather(preset[0])

    # 다음 지도 레이어를 선택하는 기능
    def next_map_layer(self, reverse=False):
        # 현재의 지도 레이어 인덱스를 업데이트합니다. 'reverse'매개변수가 True이면 이전 레이어를 선택하고, 그렇지 않으면 다음 레이어를 선택
        self.current_map_layer += -1 if reverse else 1
        self.current_map_layer %= len(self.map_layer_names)
        # 현재 선택된 지도 레이어를 가져옵니다.
        selected = self.map_layer_names[self.current_map_layer]
        # HUD를 통해 사용자에게 선택된 지도 레이어를 표시하는 알림을 보냅니다.
        self.hud.notification('LayerMap selected: %s' % selected)

    # 지도 레이어를 로드하거나 언로드하는 작업을 수행
    def load_map_layer(self, unload=False):
        # 현재 선택된 지도 레이어를 가져옵니다.
        selected = self.map_layer_names[self.current_map_layer]
        if unload:
            self.hud.notification('Unloading map layer: %s' % selected)
            self.world.unload_map_layer(selected)
        else:
            self.hud.notification('Loading map layer: %s' % selected)
            self.world.load_map_layer(selected)

    # 레이더를 토글하는 기능
    def toggle_radar(self):
        if self.radar_sensor is None:
            self.radar_sensor = RadarSensor(self.player)
        elif self.radar_sensor.sensor is not None:
            self.radar_sensor.sensor.destroy()
            self.radar_sensor = None

    def tick(self, clock):
        self.hud.tick(self, clock)

    def render(self, display):
        self.camera_manager.render(display)
        self.hud.render(display)

    def destroy_sensors(self):
        self.camera_manager.sensor.destroy()
        self.camera_manager.sensor = None
        self.camera_manager.index = None

    def destroy(self):
        if self.radar_sensor is not None:
            self.toggle_radar()
        sensors = [
            self.camera_manager.sensor,
            self.collision_sensor.sensor,
            self.obstacle_sensor.sensor,
            self.lane_invasion_sensor.sensor,
            self.gnss_sensor.sensor,
            self.imu_sensor.sensor]
        for sensor in sensors:
            if sensor is not None:
                sensor.stop()
                sensor.destroy()
        if self.player is not None:
            self.player.destroy()


# ==============================================================================
# -- KeyboardControl -----------------------------------------------------------
# ==============================================================================


class KeyboardControl(object):
    """Class that handles keyboard input."""

    def __init__(self, world, start_in_autopilot):
        self._carsim_enabled = False
        self._carsim_road = False
        self._autopilot_enabled = start_in_autopilot
        if isinstance(world.player, carla.Vehicle):
            self._control = carla.VehicleControl()
            self._lights = carla.VehicleLightState.NONE
            world.player.set_autopilot(self._autopilot_enabled)
            world.player.set_light_state(self._lights)
        elif isinstance(world.player, carla.Walker):
            self._control = carla.WalkerControl()
            self._autopilot_enabled = False
            self._rotation = world.player.get_transform().rotation
        else:
            raise NotImplementedError("Actor type not supported")
        self._steer_cache = 0.0
        world.hud.notification("Press 'H' or '?' for help.", seconds=4.0)

    def parse_events(self, client, world, clock):
        if isinstance(self._control, carla.VehicleControl):
            current_lights = self._lights
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            elif event.type == pygame.KEYUP:
                if self._is_quit_shortcut(event.key):
                    return True
                elif event.key == K_BACKSPACE:
                    if self._autopilot_enabled:
                        world.player.set_autopilot(False)
                        world.restart()
                        world.player.set_autopilot(True)
                    else:
                        world.restart()
                elif event.key == K_F1:
                    world.hud.toggle_info()
                elif event.key == K_v and pygame.key.get_mods() & KMOD_SHIFT:
                    world.next_map_layer(reverse=True)
                elif event.key == K_v:
                    world.next_map_layer()
                elif event.key == K_b and pygame.key.get_mods() & KMOD_SHIFT:
                    world.load_map_layer(unload=True)
                elif event.key == K_b:
                    world.load_map_layer()
                elif event.key == K_h or (event.key == K_SLASH and pygame.key.get_mods() & KMOD_SHIFT):
                    world.hud.help.toggle()
                elif event.key == K_TAB:
                    world.camera_manager.toggle_camera()
                elif event.key == K_c and pygame.key.get_mods() & KMOD_SHIFT:
                    world.next_weather(reverse=True)
                elif event.key == K_c:
                    world.next_weather()
                elif event.key == K_g:
                    world.toggle_radar()
                elif event.key == K_BACKQUOTE:
                    world.camera_manager.next_sensor()
                elif event.key == K_n:
                    world.camera_manager.next_sensor()
                elif event.key == K_w and (pygame.key.get_mods() & KMOD_CTRL):
                    print(world.constant_velocity_enabled)
                    if world.constant_velocity_enabled:
                        world.player.disable_constant_velocity()
                        world.constant_velocity_enabled = False
                        world.hud.notification("Disabled Constant Velocity Mode")
                        print('60 off!!')
                    else:
                        world.player.enable_constant_velocity(carla.Vector3D(1.4, 0, 0))
                        world.constant_velocity_enabled = True
                        world.hud.notification("Enabled Constant Velocity Mode at 60 km/h")
                        print('60 on!!')
                elif event.key > K_0 and event.key <= K_9:
                    world.camera_manager.set_sensor(event.key - 1 - K_0)
                elif event.key == K_r and not (pygame.key.get_mods() & KMOD_CTRL):
                    world.camera_manager.toggle_recording()
                elif event.key == K_r and (pygame.key.get_mods() & KMOD_CTRL):
                    if (world.recording_enabled):
                        client.stop_recorder()
                        world.recording_enabled = False
                        world.hud.notification("Recorder is OFF")
                    else:
                        client.start_recorder("manual_recording.rec")
                        world.recording_enabled = True
                        world.hud.notification("Recorder is ON")
                elif event.key == K_p and (pygame.key.get_mods() & KMOD_CTRL):
                    # stop recorder
                    client.stop_recorder()
                    world.recording_enabled = False
                    # work around to fix camera at start of replaying
                    current_index = world.camera_manager.index
                    world.destroy_sensors()
                    # disable autopilot
                    self._autopilot_enabled = False
                    world.player.set_autopilot(self._autopilot_enabled)
                    world.hud.notification("Replaying file 'manual_recording.rec'")
                    # replayer
                    client.replay_file("manual_recording.rec", world.recording_start, 0, 0)
                    world.camera_manager.set_sensor(current_index)
                elif event.key == K_k and (pygame.key.get_mods() & KMOD_CTRL):
                    print("k pressed")
                    world.player.enable_carsim("d:/CVC/carsim/DataUE4/ue4simfile.sim")
                elif event.key == K_j and (pygame.key.get_mods() & KMOD_CTRL):
                    self._carsim_road = not self._carsim_road
                    world.player.use_carsim_road(self._carsim_road)
                    print("j pressed, using carsim road =", self._carsim_road)
                # elif event.key == K_i and (pygame.key.get_mods() & KMOD_CTRL):
                #     print("i pressed")
                #     imp = carla.Location(z=50000)
                #     world.player.add_impulse(imp)
                elif event.key == K_MINUS and (pygame.key.get_mods() & KMOD_CTRL):
                    if pygame.key.get_mods() & KMOD_SHIFT:
                        world.recording_start -= 10
                    else:
                        world.recording_start -= 1
                    world.hud.notification("Recording start time is %d" % (world.recording_start))
                elif event.key == K_EQUALS and (pygame.key.get_mods() & KMOD_CTRL):
                    if pygame.key.get_mods() & KMOD_SHIFT:
                        world.recording_start += 10
                    else:
                        world.recording_start += 1
                    world.hud.notification("Recording start time is %d" % (world.recording_start))
                if isinstance(self._control, carla.VehicleControl):
                    if event.key == K_q:
                        self._control.gear = 1 if self._control.reverse else -1
                    elif event.key == K_m:
                        self._control.manual_gear_shift = not self._control.manual_gear_shift
                        self._control.gear = world.player.get_control().gear
                        world.hud.notification('%s Transmission' %
                                               ('Manual' if self._control.manual_gear_shift else 'Automatic'))
                    elif self._control.manual_gear_shift and event.key == K_COMMA:
                        self._control.gear = max(-1, self._control.gear - 1)
                    elif self._control.manual_gear_shift and event.key == K_PERIOD:
                        self._control.gear = self._control.gear + 1
                    elif event.key == K_p and not pygame.key.get_mods() & KMOD_CTRL:
                        self._autopilot_enabled = not self._autopilot_enabled
                        world.player.set_autopilot(self._autopilot_enabled)
                        world.hud.notification(
                            'Autopilot %s' % ('On' if self._autopilot_enabled else 'Off'))

                        # tm = client.get_trafficmanager(8000)
                        # tm.vehicle_percentage_speed_difference(world.player, 85.0)
                        # print(tm)
                    elif event.key == K_l and pygame.key.get_mods() & KMOD_CTRL:
                        current_lights ^= carla.VehicleLightState.Special1
                    elif event.key == K_l and pygame.key.get_mods() & KMOD_SHIFT:
                        current_lights ^= carla.VehicleLightState.HighBeam
                    elif event.key == K_l:
                        # Use 'L' key to switch between lights:
                        # closed -> position -> low beam -> fog
                        if not self._lights & carla.VehicleLightState.Position:
                            world.hud.notification("Position lights")
                            current_lights |= carla.VehicleLightState.Position
                        else:
                            world.hud.notification("Low beam lights")
                            current_lights |= carla.VehicleLightState.LowBeam
                        if self._lights & carla.VehicleLightState.LowBeam:
                            world.hud.notification("Fog lights")
                            current_lights |= carla.VehicleLightState.Fog
                        if self._lights & carla.VehicleLightState.Fog:
                            world.hud.notification("Lights off")
                            current_lights ^= carla.VehicleLightState.Position
                            current_lights ^= carla.VehicleLightState.LowBeam
                            current_lights ^= carla.VehicleLightState.Fog
                    elif event.key == K_i:
                        current_lights ^= carla.VehicleLightState.Interior
                    elif event.key == K_z:
                        current_lights ^= carla.VehicleLightState.LeftBlinker
                    elif event.key == K_x:
                        current_lights ^= carla.VehicleLightState.RightBlinker

        if not self._autopilot_enabled:
            if isinstance(self._control, carla.VehicleControl):
                self._parse_vehicle_keys(pygame.key.get_pressed(), clock.get_time())
                self._control.reverse = self._control.gear < 0
                # Set automatic control-related vehicle lights
                if self._control.brake:
                    current_lights |= carla.VehicleLightState.Brake
                else:  # Remove the Brake flag
                    current_lights &= ~carla.VehicleLightState.Brake
                if self._control.reverse:
                    current_lights |= carla.VehicleLightState.Reverse
                else:  # Remove the Reverse flag
                    current_lights &= ~carla.VehicleLightState.Reverse
                if current_lights != self._lights:  # Change the light state only if necessary
                    self._lights = current_lights
                    world.player.set_light_state(carla.VehicleLightState(self._lights))
            elif isinstance(self._control, carla.WalkerControl):
                self._parse_walker_keys(pygame.key.get_pressed(), clock.get_time(), world)
            world.player.apply_control(self._control)

    def _parse_vehicle_keys(self, keys, milliseconds):
        if keys[K_UP] or keys[K_w]:
            self._control.throttle = min(self._control.throttle + 0.01, 1)
        else:
            self._control.throttle = 0.0

        if keys[K_DOWN] or keys[K_s]:
            self._control.brake = min(self._control.brake + 0.2, 1)
        else:
            self._control.brake = 0

        steer_increment = 5e-4 * milliseconds
        if keys[K_LEFT] or keys[K_a]:
            if self._steer_cache > 0:
                self._steer_cache = 0
            else:
                self._steer_cache -= steer_increment
        elif keys[K_RIGHT] or keys[K_d]:
            if self._steer_cache < 0:
                self._steer_cache = 0
            else:
                self._steer_cache += steer_increment
        else:
            self._steer_cache = 0.0
        self._steer_cache = min(0.7, max(-0.7, self._steer_cache))
        self._control.steer = round(self._steer_cache, 1)
        self._control.hand_brake = keys[K_SPACE]

    def _parse_walker_keys(self, keys, milliseconds, world):
        self._control.speed = 0.0
        if keys[K_DOWN] or keys[K_s]:
            self._control.speed = 0.0
        if keys[K_LEFT] or keys[K_a]:
            self._control.speed = .01
            self._rotation.yaw -= 0.08 * milliseconds
        if keys[K_RIGHT] or keys[K_d]:
            self._control.speed = .01
            self._rotation.yaw += 0.08 * milliseconds
        if keys[K_UP] or keys[K_w]:
            self._control.speed = world.player_max_speed_fast if pygame.key.get_mods() & KMOD_SHIFT else world.player_max_speed
        self._control.jump = keys[K_SPACE]
        self._rotation.yaw = round(self._rotation.yaw, 1)
        self._control.direction = self._rotation.get_forward_vector()

    @staticmethod
    def _is_quit_shortcut(key):
        return (key == K_ESCAPE) or (key == K_q and pygame.key.get_mods() & KMOD_CTRL)


# ==============================================================================
# -- HUD -----------------------------------------------------------------------
# ==============================================================================


class HUD(object):
    def __init__(self, width, height):
        self.dim = (width, height)
        font = pygame.font.Font(pygame.font.get_default_font(), 20)
        font_name = 'courier' if os.name == 'nt' else 'mono'
        fonts = [x for x in pygame.font.get_fonts() if font_name in x]
        default_font = 'ubuntumono'
        mono = default_font if default_font in fonts else fonts[0]
        mono = pygame.font.match_font(mono)
        self._font_mono = pygame.font.Font(mono, 12 if os.name == 'nt' else 14)
        self._notifications = FadingText(font, (width, 40), (0, height - 40))
        # self.help = HelpText(pygame.font.Font(mono, 16), width, height)
        self.server_fps = 0
        self.frame = 0
        self.simulation_time = 0
        self._show_info = True
        self._info_text = []
        self._server_clock = pygame.time.Clock()

    def on_world_tick(self, timestamp):
        self._server_clock.tick()
        self.server_fps = self._server_clock.get_fps()
        self.frame = timestamp.frame
        self.simulation_time = timestamp.elapsed_seconds

    def tick(self, world, clock):
        self._notifications.tick(world, clock)
        if not self._show_info:
            return
        t = world.player.get_transform()
        v = world.player.get_velocity()
        c = world.player.get_control()
        compass = world.imu_sensor.compass
        heading = 'N' if compass > 270.5 or compass < 89.5 else ''
        heading += 'S' if 90.5 < compass < 269.5 else ''
        heading += 'E' if 0.5 < compass < 179.5 else ''
        heading += 'W' if 180.5 < compass < 359.5 else ''
        colhist = world.collision_sensor.get_collision_history()
        collision = [colhist[x + self.frame - 200] for x in range(0, 200)]
        max_col = max(1.0, max(collision))
        collision = [x / max_col for x in collision]
        vehicles = world.world.get_actors().filter('vehicle.*')
        self._info_text = [
            'Server:  % 16.0f FPS' % self.server_fps,
            'Client:  % 16.0f FPS' % clock.get_fps(),
            '',
            'Vehicle: % 20s' % get_actor_display_name(world.player, truncate=20),
            'Map:     % 20s' % world.map.name.split('/')[-1],
            'Simulation time: % 12s' % datetime.timedelta(seconds=int(self.simulation_time)),
            '',
            'Speed:   % 15.0f km/h' % (3.6 * math.sqrt(v.x ** 2 + v.y ** 2 + v.z ** 2)),
            u'Compass:% 17.0f\N{DEGREE SIGN} % 2s' % (compass, heading),
            'Accelero: (%5.1f,%5.1f,%5.1f)' % (world.imu_sensor.accelerometer),
            'Gyroscop: (%5.1f,%5.1f,%5.1f)' % (world.imu_sensor.gyroscope),
            'Location:% 20s' % ('(% 5.1f, % 5.1f)' % (t.location.x, t.location.y)),
            'GNSS:% 24s' % ('(% 2.6f, % 3.6f)' % (world.gnss_sensor.lat, world.gnss_sensor.lon)),
            'Height:  % 18.0f m' % t.location.z,
            '']
        if isinstance(c, carla.VehicleControl):
            self._info_text += [
                ('Throttle:', c.throttle, 0.0, 1.0),
                ('Steer:', c.steer, -1.0, 1.0),
                ('Brake:', c.brake, 0.0, 1.0),
                ('Reverse:', c.reverse),
                ('Hand brake:', c.hand_brake),
                ('Manual:', c.manual_gear_shift),
                'Gear:        %s' % {-1: 'R', 0: 'N'}.get(c.gear, c.gear)]
        elif isinstance(c, carla.WalkerControl):
            self._info_text += [
                ('Speed:', c.speed, 0.0, 5.556),
                ('Jump:', c.jump)]
        self._info_text += [
            '',
            'Collision:',
            collision,
            '',
            'Number of vehicles: % 8d' % len(vehicles)]
        if len(vehicles) > 1:
            self._info_text += ['Nearby vehicles:']
            distance = lambda l: math.sqrt(
                (l.x - t.location.x) ** 2 + (l.y - t.location.y) ** 2 + (l.z - t.location.z) ** 2)
            vehicles = [(distance(x.get_location()), x) for x in vehicles if x.id != world.player.id]
            for d, vehicle in sorted(vehicles, key=lambda vehicles: vehicles[0]):
                if d > 200.0:
                    break
                vehicle_type = get_actor_display_name(vehicle, truncate=22)
                self._info_text.append('% 4dm %s' % (d, vehicle_type))

    def toggle_info(self):
        self._show_info = not self._show_info

    def notification(self, text, seconds=2.0):
        self._notifications.set_text(text, seconds=seconds)

    def error(self, text):
        self._notifications.set_text('Error: %s' % text, (255, 0, 0))

    def render(self, display):
        if self._show_info:
            info_surface = pygame.Surface((220, self.dim[1]))
            info_surface.set_alpha(100)
            display.blit(info_surface, (0, 0))
            v_offset = 4
            bar_h_offset = 100
            bar_width = 106
            for item in self._info_text:
                if v_offset + 18 > self.dim[1]:
                    break
                if isinstance(item, list):
                    if len(item) > 1:
                        points = [(x + 8, v_offset + 8 + (1.0 - y) * 30) for x, y in enumerate(item)]
                        pygame.draw.lines(display, (255, 136, 0), False, points, 2)
                    item = None
                    v_offset += 18
                elif isinstance(item, tuple):
                    if isinstance(item[1], bool):
                        rect = pygame.Rect((bar_h_offset, v_offset + 8), (6, 6))
                        pygame.draw.rect(display, (255, 255, 255), rect, 0 if item[1] else 1)
                    else:
                        rect_border = pygame.Rect((bar_h_offset, v_offset + 8), (bar_width, 6))
                        pygame.draw.rect(display, (255, 255, 255), rect_border, 1)
                        f = (item[1] - item[2]) / (item[3] - item[2])
                        if item[2] < 0.0:
                            rect = pygame.Rect((bar_h_offset + f * (bar_width - 6), v_offset + 8), (6, 6))
                        else:
                            rect = pygame.Rect((bar_h_offset, v_offset + 8), (f * bar_width, 6))
                        pygame.draw.rect(display, (255, 255, 255), rect)
                    item = item[0]
                if item:  # At this point has to be a str.
                    surface = self._font_mono.render(item, True, (255, 255, 255))
                    display.blit(surface, (8, v_offset))
                v_offset += 18
        self._notifications.render(display)
        # self.help.render(display)


# ==============================================================================
# -- FadingText ----------------------------------------------------------------
# ==============================================================================


class FadingText(object):
    def __init__(self, font, dim, pos):
        self.font = font
        self.dim = dim
        self.pos = pos
        self.seconds_left = 0
        self.surface = pygame.Surface(self.dim)

    def set_text(self, text, color=(255, 255, 255), seconds=2.0):
        text_texture = self.font.render(text, True, color)
        self.surface = pygame.Surface(self.dim)
        self.seconds_left = seconds
        self.surface.fill((0, 0, 0, 0))
        self.surface.blit(text_texture, (10, 11))

    def tick(self, _, clock):
        delta_seconds = 1e-3 * clock.get_time()
        self.seconds_left = max(0.0, self.seconds_left - delta_seconds)
        self.surface.set_alpha(500.0 * self.seconds_left)

    def render(self, display):
        display.blit(self.surface, self.pos)


# ==============================================================================
# -- HelpText ------------------------------------------------------------------
# ==============================================================================


class HelpText(object):
    """Helper class to handle text output using pygame"""

    def __init__(self, font, width, height):
        lines = __doc__.split('\n')
        self.font = font
        self.line_space = 18
        self.dim = (780, len(lines) * self.line_space + 12)
        self.pos = (0.5 * width - 0.5 * self.dim[0], 0.5 * height - 0.5 * self.dim[1])
        self.seconds_left = 0
        self.surface = pygame.Surface(self.dim)
        self.surface.fill((0, 0, 0, 0))
        for n, line in enumerate(lines):
            text_texture = self.font.render(line, True, (255, 255, 255))
            self.surface.blit(text_texture, (22, n * self.line_space))
            self._render = False
        self.surface.set_alpha(220)

    def toggle(self):
        self._render = not self._render

    def render(self, display):
        if self._render:
            display.blit(self.surface, self.pos)


# ==============================================================================
# -- Sensor -----------------------------------------------------------
# ==============================================================================


class CollisionSensor(object):
    def __init__(self, parent_actor, hud):
        self.sensor = None
        self.history = []
        self._parent = parent_actor
        self.hud = hud
        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.other.collision')
        self.sensor = world.spawn_actor(bp, carla.Transform(), attach_to=self._parent)
        # We need to pass the lambda a weak reference to self to avoid circular
        # reference.
        weak_self = weakref.ref(self)
        self.sensor.listen(lambda event: CollisionSensor._on_collision(weak_self, event))

    def get_collision_history(self):
        history = collections.defaultdict(int)
        for frame, intensity in self.history:
            history[frame] += intensity
        return history

    @staticmethod
    def _on_collision(weak_self, event):
        self = weak_self()
        if not self:
            return
        actor_type = get_actor_display_name(event.other_actor)
        self.hud.notification('Collision with %r' % actor_type)
        impulse = event.normal_impulse
        intensity = math.sqrt(impulse.x ** 2 + impulse.y ** 2 + impulse.z ** 2)
        self.history.append((event.frame, intensity))
        if len(self.history) > 4000:
            self.history.pop(0)


class LineOfSightSensor(object):
    def __init__(self, parent_actor, hud):
        self.sensor = None
        self._history = []
        self._parent = parent_actor
        self._hud = hud
        self._event_count = 0
        self.sensor_transform = carla.Transform(carla.Location(x=1.6, z=1.7),
                                                carla.Rotation(yaw=0))  # Put this sensor on the windshield of the car.
        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.other.obstacle')
        bp.set_attribute('distance', '200')
        bp.set_attribute('hit_radius', '12')
        bp.set_attribute('only_dynamics', 'true')
        # bp.set_attribute('debug_linetrace', 'true')
        bp.set_attribute('sensor_tick', '0.5')
        self.sensor = world.spawn_actor(bp, self.sensor_transform, attach_to=self._parent)
        weak_self = weakref.ref(self)
        self.sensor.listen(lambda event: LineOfSightSensor._on_LOS(weak_self, event))

    @staticmethod
    def _on_LOS(weak_self, event, some_condition=None):
        self = weak_self()
        if not self:
            return
        print(str(event.other_actor))
        if event.other_actor.type_id.startswith('vehicle.') or event.other_actor.type_id.startswith('walker.'):
            print("Event %s, in line of sight with %s at distance %u" % (
            self._event_count, event.other_actor.type_id, event.distance))
            self._event_count += 1

            if event.other_actor.is_alive:
                try:
                    if some_condition:
                        event.other_actor.destroy()
                except RuntimeError as e:
                    print("Error deleting actor: {}".format(e))
            else:
                print("Actor is already destroyed or in the process of being destroyed.")

    def update(self, delta_seconds, event, actors_to_delete=None):
        self._on_LOS(event)

        for actor in actors_to_delete:
            if actor.is_alive:
                try:
                    actor.destroy()
                except RuntimeError as e:
                    print("Error deleting actor: {}".format(e))


# ==============================================================================
# -- LaneInvasionSensor --------------------------------------------------------
# ==============================================================================


class LaneInvasionSensor(object):
    def __init__(self, parent_actor, hud):
        self.sensor = None
        self._parent = parent_actor
        self.hud = hud
        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.other.lane_invasion')
        self.sensor = world.spawn_actor(bp, carla.Transform(), attach_to=self._parent)
        # We need to pass the lambda a weak reference to self to avoid circular
        # reference.
        weak_self = weakref.ref(self)
        self.sensor.listen(lambda event: LaneInvasionSensor._on_invasion(weak_self, event))

    @staticmethod
    def _on_invasion(weak_self, event):
        self = weak_self()
        if not self:
            return
        lane_types = set(x.type for x in event.crossed_lane_markings)
        text = ['%r' % str(x).split()[-1] for x in lane_types]
        self.hud.notification('Crossed line %s' % ' and '.join(text))


# ==============================================================================
# -- GnssSensor ----------------------------------------------------------------
# ==============================================================================


class GnssSensor(object):
    def __init__(self, parent_actor):
        self.sensor = None
        self._parent = parent_actor
        self.lat = 0.0
        self.lon = 0.0
        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.other.gnss')
        self.sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=1.0, z=2.8)), attach_to=self._parent)
        # We need to pass the lambda a weak reference to self to avoid circular
        # reference.
        weak_self = weakref.ref(self)
        self.sensor.listen(lambda event: GnssSensor._on_gnss_event(weak_self, event))

    @staticmethod
    def _on_gnss_event(weak_self, event):
        self = weak_self()
        if not self:
            return
        self.lat = event.latitude
        self.lon = event.longitude


# ==============================================================================
# -- IMUSensor -----------------------------------------------------------------
# ==============================================================================


class IMUSensor(object):
    def __init__(self, parent_actor):
        self.sensor = None
        self._parent = parent_actor
        self.accelerometer = (0.0, 0.0, 0.0)
        self.gyroscope = (0.0, 0.0, 0.0)
        self.compass = 0.0
        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.other.imu')
        self.sensor = world.spawn_actor(
            bp, carla.Transform(), attach_to=self._parent)
        # We need to pass the lambda a weak reference to self to avoid circular
        # reference.
        weak_self = weakref.ref(self)
        self.sensor.listen(
            lambda sensor_data: IMUSensor._IMU_callback(weak_self, sensor_data))

    @staticmethod
    def _IMU_callback(weak_self, sensor_data):
        self = weak_self()
        if not self:
            return
        limits = (-99.9, 99.9)
        self.accelerometer = (
            max(limits[0], min(limits[1], sensor_data.accelerometer.x)),
            max(limits[0], min(limits[1], sensor_data.accelerometer.y)),
            max(limits[0], min(limits[1], sensor_data.accelerometer.z)))
        self.gyroscope = (
            max(limits[0], min(limits[1], math.degrees(sensor_data.gyroscope.x))),
            max(limits[0], min(limits[1], math.degrees(sensor_data.gyroscope.y))),
            max(limits[0], min(limits[1], math.degrees(sensor_data.gyroscope.z))))
        self.compass = math.degrees(sensor_data.compass)


# ==============================================================================
# -- RadarSensor ---------------------------------------------------------------
# ==============================================================================


class RadarSensor(object):
    def __init__(self, parent_actor):
        self.sensor = None
        self._parent = parent_actor
        self.velocity_range = 7.5  # m/s
        world = self._parent.get_world()
        self.debug = world.debug
        bp = world.get_blueprint_library().find('sensor.other.radar')
        bp.set_attribute('horizontal_fov', str(35))
        bp.set_attribute('vertical_fov', str(20))
        self.sensor = world.spawn_actor(
            bp,
            carla.Transform(
                carla.Location(x=2.8, z=1.0),
                carla.Rotation(pitch=5)),
            attach_to=self._parent)
        # We need a weak reference to self to avoid circular reference.
        weak_self = weakref.ref(self)
        self.sensor.listen(
            lambda radar_data: RadarSensor._Radar_callback(weak_self, radar_data))

    @staticmethod
    def _Radar_callback(weak_self, radar_data):
        self = weak_self()
        if not self:
            return
        # To get a numpy [[vel, altitude, azimuth, depth],...[,,,]]:
        # points = np.frombuffer(radar_data.raw_data, dtype=np.dtype('f4'))
        # points = np.reshape(points, (len(radar_data), 4))

        current_rot = radar_data.transform.rotation
        for detect in radar_data:
            azi = math.degrees(detect.azimuth)
            alt = math.degrees(detect.altitude)
            # The 0.25 adjusts a bit the distance so the dots can
            # be properly seen
            fw_vec = carla.Vector3D(x=detect.depth - 0.25)
            carla.Transform(
                carla.Location(),
                carla.Rotation(
                    pitch=current_rot.pitch + alt,
                    yaw=current_rot.yaw + azi,
                    roll=current_rot.roll)).transform(fw_vec)

            def clamp(min_v, max_v, value):
                return max(min_v, min(value, max_v))

            norm_velocity = detect.velocity / self.velocity_range  # range [-1, 1]
            r = int(clamp(0.0, 1.0, 1.0 - norm_velocity) * 255.0)
            g = int(clamp(0.0, 1.0, 1.0 - abs(norm_velocity)) * 255.0)
            b = int(abs(clamp(- 1.0, 0.0, - 1.0 - norm_velocity)) * 255.0)
            self.debug.draw_point(
                radar_data.transform.location + fw_vec,
                size=0.075,
                life_time=0.06,
                persistent_lines=False,
                color=carla.Color(r, g, b))


# ==============================================================================
# -- CameraManager -------------------------------------------------------------
# ==============================================================================


class CameraManager(object):
    def __init__(self, parent_actor, hud, gamma_correction):
        self.sensor = None
        self.surface = None
        self._parent = parent_actor
        self.hud = hud
        self.recording = False
        bound_y = 0.5 + self._parent.bounding_box.extent.y
        Attachment = carla.AttachmentType
        self._camera_transforms = [
            (carla.Transform(carla.Location(x=-5.5, z=2.5), carla.Rotation(pitch=8.0)), Attachment.Rigid),
            (carla.Transform(carla.Location(x=1.6, z=1.7)), Attachment.Rigid),
            (carla.Transform(carla.Location(x=5.5, y=1.5, z=1.5)), Attachment.Rigid),
            (carla.Transform(carla.Location(x=-8.0, z=6.0), carla.Rotation(pitch=6.0)), Attachment.Rigid),
            (carla.Transform(carla.Location(x=-1, y=-bound_y, z=0.5)), Attachment.Rigid)]
        self.transform_index = 1
        self.sensors = [
            ['sensor.camera.rgb', cc.Raw, 'Camera RGB', {}],
            ['sensor.camera.depth', cc.Raw, 'Camera Depth (Raw)', {}],
            ['sensor.camera.depth', cc.Depth, 'Camera Depth (Gray Scale)', {}],
            ['sensor.camera.depth', cc.LogarithmicDepth, 'Camera Depth (Logarithmic Gray Scale)', {}],
            ['sensor.camera.semantic_segmentation', cc.Raw, 'Camera Semantic Segmentation (Raw)', {}],
            ['sensor.camera.semantic_segmentation', cc.CityScapesPalette,
             'Camera Semantic Segmentation (CityScapes Palette)', {}],
            ['sensor.lidar.ray_cast', None, 'Lidar (Ray-Cast)', {'range': '50'}],
            ['sensor.camera.dvs', cc.Raw, 'Dynamic Vision Sensor', {}],
            ['sensor.camera.rgb', cc.Raw, 'Camera RGB Distorted',
             {'lens_circle_multiplier': '3.0',
              'lens_circle_falloff': '3.0',
              'chromatic_aberration_intensity': '0.5',
              'chromatic_aberration_offset': '0'}]]
        world = self._parent.get_world()
        bp_library = world.get_blueprint_library()
        for item in self.sensors:
            bp = bp_library.find(item[0])
            if item[0].startswith('sensor.camera'):
                bp.set_attribute('image_size_x', str(hud.dim[0]))
                bp.set_attribute('image_size_y', str(hud.dim[1]))
                if bp.has_attribute('gamma'):
                    bp.set_attribute('gamma', str(gamma_correction))
                for attr_name, attr_value in item[3].items():
                    bp.set_attribute(attr_name, attr_value)
            elif item[0].startswith('sensor.lidar'):
                self.lidar_range = 50

                for attr_name, attr_value in item[3].items():
                    bp.set_attribute(attr_name, attr_value)
                    if attr_name == 'range':
                        self.lidar_range = float(attr_value)

            item.append(bp)
        self.index = None

    def toggle_camera(self):
        self.transform_index = (self.transform_index + 1) % len(self._camera_transforms)
        self.set_sensor(self.index, notify=False, force_respawn=True)

    def set_sensor(self, index, notify=True, force_respawn=False):
        index = index % len(self.sensors)
        needs_respawn = True if self.index is None else \
            (force_respawn or (self.sensors[index][2] != self.sensors[self.index][2]))
        if needs_respawn:
            if self.sensor is not None:
                self.sensor.destroy()
                self.surface = None
            self.sensor = self._parent.get_world().spawn_actor(
                self.sensors[index][-1],
                self._camera_transforms[self.transform_index][0],
                attach_to=self._parent,
                attachment_type=self._camera_transforms[self.transform_index][1])
            # We need to pass the lambda a weak reference to self to avoid
            # circular reference.
            weak_self = weakref.ref(self)
            self.sensor.listen(lambda image: CameraManager._parse_image(weak_self, image))
        if notify:
            self.hud.notification(self.sensors[index][2])
        self.index = index

    def next_sensor(self):
        self.set_sensor(self.index + 1)

    def toggle_recording(self):
        self.recording = not self.recording
        self.hud.notification('Recording %s' % ('On' if self.recording else 'Off'))

    def render(self, display):
        if self.surface is not None:
            display.blit(self.surface, (0, 0))

    @staticmethod
    def _parse_image(weak_self, image):
        self = weak_self()
        if not self:
            return
        if self.sensors[self.index][0].startswith('sensor.lidar'):
            points = np.frombuffer(image.raw_data, dtype=np.dtype('f4'))
            points = np.reshape(points, (int(points.shape[0] / 4), 4))
            lidar_data = np.array(points[:, :2])
            lidar_data *= min(self.hud.dim) / (2.0 * self.lidar_range)
            lidar_data += (0.5 * self.hud.dim[0], 0.5 * self.hud.dim[1])
            lidar_data = np.fabs(lidar_data)  # pylint: disable=E1111
            lidar_data = lidar_data.astype(np.int32)
            lidar_data = np.reshape(lidar_data, (-1, 2))
            lidar_img_size = (self.hud.dim[0], self.hud.dim[1], 3)
            lidar_img = np.zeros((lidar_img_size), dtype=np.uint8)
            lidar_img[tuple(lidar_data.T)] = (155, 155, 5)
            self.surface = pygame.surfarray.make_surface(lidar_img)
        elif self.sensors[self.index][0].startswith('sensor.camera.dvs'):
            # Example of converting the raw_data from a carla.DVSEventArray
            # sensor into a NumPy array and using it as an image
            dvs_events = np.frombuffer(image.raw_data, dtype=np.dtype([
                ('x', np.uint16), ('y', np.uint16), ('t', np.int64), ('pol', np.bool)]))
            dvs_img = np.zeros((image.height, image.width, 3), dtype=np.uint8)
            # Blue is positive, red is negative
            dvs_img[dvs_events[:]['y'], dvs_events[:]['x'], dvs_events[:]['pol'] * 2] = 255
            self.surface = pygame.surfarray.make_surface(dvs_img.swapaxes(0, 1))
        else:
            image.convert(self.sensors[self.index][1])
            array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
            array = np.reshape(array, (image.height, image.width, 4))
            array = array[:, :, :3]
            array = array[:, :, ::-1]
            self.surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))
        if self.recording:
            image.save_to_disk('_out/%08d' % image.frame)


# ==============================================================================
# -- game_loop() ---------------------------------------------------------------
# ==============================================================================
def game_loop(args):
    pygame.init()
    pygame.font.init()
    world = None

    before_time = time.time()
    before_w = None
    current_w = None

    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(2.0)

        display = pygame.display.set_mode(
            (args.width, args.height),
            pygame.HWSURFACE | pygame.DOUBLEBUF)

        hud = HUD(args.width, args.height)
        world = World(client.get_world(), hud, args)
        debug = client.get_world().debug
        controller = KeyboardControl(world, args.autopilot)

        clock = pygame.time.Clock()

        map = world.world.get_map()
        vehicle = world.player

        tm = client.get_trafficmanager(8000)
        tm.vehicle_percentage_speed_difference(world.player, 85.0)
        tm.distance_to_leading_vehicle(world.player, 10)

        current_w = map.get_waypoint(vehicle.get_location())
        before_w = current_w
        current_w = map.get_waypoint(vehicle.get_location())
        while True:
            clock.tick_busy_loop(60)
            if controller.parse_events(client, world, clock):
                return
            world.tick(clock)
            world.render(display)

            if vehicle.is_alive:
                # location = vehicle.get_location()
                # current_w = map.get_waypoint(location)
                # print(
                #     "X_coordinate: %s, " % location.x +
                #     "Y_coordinate: %s, " % location.y +
                #     "Z_coordinate: %s, " % location.z +
                #     "Waypoint_ID: %s" % current_w.id)
                # "x: %s, " % current_w.x +
                # "y: %s, " % current_w.y +
                # "z: %s, " & current_w.z)

                potential_w_list = []
                potential_w = map.get_waypoint(vehicle.get_location(),
                                               lane_type=carla.LaneType.Driving | carla.LaneType.Shoulder | carla.LaneType.Sidewalk)
                potential_w_list.append(potential_w)
                # print('current: ', current_w)
                # check for available right driving lanes
                # if current_w.lane_change & carla.LaneChange.Right:
                #
                #     right_w = current_w.get_right_lane()
                #     # print('right: ', right_w)
                #     if right_w and right_w.lane_type == carla.LaneType.Driving:
                #         potential_w_list.append(right_w)
                #         # potential_w += list(right_w.next(waypoint_separation))
                #
                # # check for available left driving lanes
                # if current_w.lane_change & carla.LaneChange.Left:
                #
                #     left_w = current_w.get_left_lane()
                #     # print('left: ', left_w)
                #     if left_w and left_w.lane_type == carla.LaneType.Driving:
                #         potential_w_list.append(left_w)
                #         # potential_w += list(left_w.next(waypoint_separation))

                # choose a random waypoint to be the next
                # chosen_w = random.choice(potential_w_list)
                next_w = random.choice(potential_w_list)
                # p = next_w.get_landmarks(potential_w, distance=10.0)
                # print(p)
                # next_w = random.choice(chosen_w.next(waypoint_separation))
                # potential_w.remove(next_w)
                # next_w = map.get_waypoint(vehicle.get_location(), lane_type=carla.LaneType.Driving | carla.LaneType.Shoulder | carla.LaneType.Sidewalk)
                # Check if the vehicle is moving
                if next_w.id != current_w.id:

                    # if current_w.lane_change & carla.LaneChange.Right:
                    #
                    #     right_w = current_w.get_right_lane()
                    #     # print('right: ', right_w)
                    #     if right_w and right_w.lane_type == carla.LaneType.Driving:
                    #         print('right')
                    #         # potential_w_list.append(right_w)
                    #         # potential_w += list(right_w.next(waypoint_separation))
                    #
                    #     # check for available left driving lanes
                    # if current_w.lane_change & carla.LaneChange.Left:
                    #
                    #     left_w = current_w.get_left_lane()
                    #     # print('left: ', left_w)
                    #     if left_w and left_w.lane_type == carla.LaneType.Driving:
                    #         print('left')
                    #         # potential_w_list.append(left_w)
                    #         # potential_w += list(left_w.next(waypoint_separation))

                    vector = vehicle.get_velocity()
                    # Check if the vehicle is on a sidewalk
                    if time.time() - before_time >= 6:
                        location = vehicle.get_location()
                        current_w = map.get_waypoint(location)
                        previous_waypoint_x = current_w.transform.location.x
                        previous_waypoint_y = current_w.transform.location.y
                        previous_waypoint_z = current_w.transform.location.z
                        print(
                            "X_coordinate: %s, " % previous_waypoint_x +
                            "Y_coordinate: %s, " % previous_waypoint_y +
                            "Z_coordinate: %s, " % previous_waypoint_z +
                            "Waypoint_ID: %s" % current_w.id)

                        csv_repo = CsvCoordinateRepositoryImpl.getInstance()
                        csv_repo.saveCoordinateInCsv(
                            work_id="1234",
                            x_coordinate=previous_waypoint_x,
                            y_coordinate=previous_waypoint_y,
                            z_coordinate=previous_waypoint_z,
                            wayPointId=current_w.id,
                            townNumber="Town01"
                        )

                        if current_w.lane_change & carla.LaneChange.Right:

                            right_w = current_w.get_right_lane()
                            # print('right: ', right_w)
                            if right_w and right_w.lane_type == carla.LaneType.Driving:
                                potential_w_list.append(right_w)
                                # potential_w += list(right_w.next(waypoint_separation))

                            # check for available left driving lanes
                        if current_w.lane_change & carla.LaneChange.Left:

                            left_w = current_w.get_left_lane()
                            # print('left: ', left_w)
                            if left_w and left_w.lane_type == carla.LaneType.Driving:
                                potential_w_list.append(left_w)
                                # potential_w += list(left_w.next(waypoint_separation))

                            # choose a random waypoint to be the next
                            # chosen_w = random.choice(potential_w_list)
                        next_w = random.choice(potential_w_list)

                        if next_w != potential_w:
                            if current_w.lane_change & carla.LaneChange.Right:
                                tm.force_lane_change(vehicle, True)
                            elif current_w.lane_change & carla.LaneChange.Left:
                                tm.force_lane_change(vehicle, False)

                        if current_w.lane_type == carla.LaneType.Sidewalk:

                            draw_waypoint_union(debug, before_w, current_w, cyan if current_w.is_junction else red, 60)
                            # draw_waypoint_union(debug, current_w, next_w, red if current_w.is_junction else red, 60)
                            draw_waypoint_union(debug, current_w, random.choice(next_w.next(waypoint_separation)),
                                                red if current_w.is_junction else red, 60)
                        else:

                            draw_waypoint_union(debug, before_w, current_w, cyan if current_w.is_junction else green,
                                                60)
                            # draw_waypoint_union(debug, current_w, next_w, red if current_w.is_junction else red, 60)
                            draw_waypoint_union(debug, current_w, random.choice(next_w.next(waypoint_separation)),
                                                red if current_w.is_junction else red, 60)
                        # print(time.time())
                        # print(next_w.next(waypoint_separation))
                        debug.draw_string(current_w.transform.location, str('%15.0f km/h' % (
                                    3.6 * math.sqrt(vector.x ** 2 + vector.y ** 2 + vector.z ** 2))), False, orange, 60)
                        draw_transform(debug, current_w.transform, white, 60)

                        before_time = time.time()
                        before_w = current_w

                # Update the current waypoint and sleep for some time
                current_w = next_w
            pygame.display.flip()

            # list of potential next waypoints
            # potential_w = list(current_w.next(waypoint_separation))

            # # check for available right driving lanes
            # if current_w.lane_change & carla.LaneChange.Right:
            #     right_w = current_w.get_right_lane()
            #     if right_w and right_w.lane_type == carla.LaneType.Driving:
            #         potential_w += list(right_w.next(waypoint_separation))
            #
            # # check for available left driving lanes
            # if current_w.lane_change & carla.LaneChange.Left:
            #     left_w = current_w.get_left_lane()
            #     if left_w and left_w.lane_type == carla.LaneType.Driving:
            #         potential_w += list(left_w.next(waypoint_separation))
            #
            # # choose a random waypoint to be the next
            # next_w = random.choice(potential_w)
            # potential_w.remove(next_w)
            #
            # # Render some nice information, notice that you can't see the strings if you are using an editor camera
            # if args.info:
            #     draw_waypoint_info(debug, current_w, trail_life_time)
            # draw_waypoint_union(debug, current_w, next_w, cyan if current_w.is_junction else green, trail_life_time)
            # draw_transform(debug, current_w.transform, white, trail_life_time)
            #
            # # print the remaining waypoints
            # for p in potential_w:
            #     draw_waypoint_union(debug, current_w, p, red, trail_life_time)
            #     draw_transform(debug, p.transform, white, trail_life_time)
            #
            # # draw all junction waypoints and bounding box
            # if next_w.is_junction:
            #     junction = next_w.get_junction()
            #     draw_junction(debug, junction, trail_life_time)
            #
            # # update the current waypoint and sleep for some time
            # current_w = next_w

    finally:

        if (world and world.recording_enabled):
            client.stop_recorder()

        if world is not None:
            world.destroy()

        pygame.quit()


# def game_loop(args):
#     pygame.init()
#     pygame.font.init()
#     world = None
#
#     try:
#         client = carla.Client(args.host, args.port)
#         client.set_timeout(2.0)
#
#         display = pygame.display.set_mode(
#             (args.width, args.height),
#             pygame.HWSURFACE | pygame.DOUBLEBUF)
#
#         hud = HUD(args.width, args.height)
#         world = World(client.get_world(), hud, args)
#         controller = KeyboardControl(world, args.autopilot)
#
#         clock = pygame.time.Clock()
#         while True:
#             clock.tick_busy_loop(60)
#             if controller.parse_events(client, world, clock):
#                 return
#             world.tick(clock)
#             world.render(display)
#             pygame.display.flip()
#
#     finally:
#
#         if (world and world.recording_enabled):
#             client.stop_recorder()
#
#         if world is not None:
#             world.destroy()
#
#         pygame.quit()


# ==============================================================================
# -- main() --------------------------------------------------------------------
# ==============================================================================


def main():
    argparser = argparse.ArgumentParser(
        description='CARLA Manual Control Client')
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='debug',
        help='print debug information')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '-a', '--autopilot',
        action='store_true',
        help='enable autopilot')
    argparser.add_argument(
        '--res',
        metavar='WIDTHxHEIGHT',
        default='1280x720',
        help='window resolution (default: 1280x720)')
    argparser.add_argument(
        '--filter',
        metavar='PATTERN',
        default='vehicle.*',
        help='actor filter (default: "vehicle.*")')
    argparser.add_argument(
        '--rolename',
        metavar='NAME',
        default='hero',
        help='actor role name (default: "hero")')
    argparser.add_argument(
        '--gamma',
        default=2.2,
        type=float,
        help='Gamma correction of the camera (default: 2.2)')
    argparser.add_argument(
        '-i', '--info',
        action='store_true',
        help='Show text information')
    args = argparser.parse_args()

    args.width, args.height = [int(x) for x in args.res.split('x')]

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)

    print(__doc__)

    try:

        game_loop(args)

    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')


if __name__ == '__main__':
    main()
