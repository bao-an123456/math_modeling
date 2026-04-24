"""参数配置模块"""

# 车辆类型: (名称, 载重kg, 容积m³, 可用数量, 是否新能源)
VEHICLE_TYPES = [
    {"name": "燃油车A", "cap_w": 3000, "cap_v": 13.5, "count": 60, "is_ev": False},
    {"name": "燃油车B", "cap_w": 1500, "cap_v": 10.8, "count": 50, "is_ev": False},
    {"name": "燃油车C", "cap_w": 1250, "cap_v": 6.5,  "count": 50, "is_ev": False},
    {"name": "新能源A", "cap_w": 3000, "cap_v": 15.0, "count": 10, "is_ev": True},
    {"name": "新能源B", "cap_w": 1250, "cap_v": 8.5,  "count": 15, "is_ev": True},
]

START_COST = 400.0
FUEL_PRICE = 7.61
ELEC_PRICE = 1.64
CARBON_PRICE = 0.65
ETA_FUEL = 2.547
GAMMA_ELEC = 0.501
WAIT_COST_RATE = 20.0
LATE_COST_RATE = 50.0
SERVICE_TIME = 20.0 / 60.0  # 小时
FUEL_LOAD_EXTRA = 0.40
EV_LOAD_EXTRA = 0.35
EARLIEST_DEPART = 8.0
DEFAULT_SPEED = 35.4

# 时段速度
SPEED_PERIODS = [
    (8.0,  9.0,  9.8),
    (9.0,  10.0, 55.3),
    (10.0, 11.5, 35.4),
    (11.5, 13.0, 9.8),
    (13.0, 15.0, 55.3),
    (15.0, 17.0, 35.4),
]

# ALNS参数
ALNS_ITER = 3000
ALNS_SEG = 100
ALNS_REM_MIN = 0.10
ALNS_REM_MAX = 0.30
ALNS_TEMP_FACTOR = 0.05
ALNS_COOL = 0.9995
ALNS_S1, ALNS_S2, ALNS_S3 = 33, 9, 2
ALNS_DECAY = 0.8
SEED = 42
