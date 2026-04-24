"""工具函数模块: 速度、旅行时间、能耗计算"""
import math
from vrp_config import *


def get_speed(t):
    """获取时刻t(小时)的行驶速度(km/h)"""
    for s, e, v in SPEED_PERIODS:
        if s <= t < e:
            return v
    return DEFAULT_SPEED


def _next_boundary(t):
    """获取t之后最近的时段边界"""
    bounds = sorted(set(s for s, e, v in SPEED_PERIODS) | set(e for s, e, v in SPEED_PERIODS))
    for b in bounds:
        if b > t + 1e-9:
            return b
    return 24.0


def travel_time(dist, depart_t):
    """计算考虑时变速度的旅行时间(小时)"""
    if dist < 1e-9:
        return 0.0
    rem = dist
    t = depart_t
    for _ in range(50):
        if rem < 1e-9:
            break
        spd = get_speed(t)
        if spd < 0.5:
            spd = 0.5
        nb = _next_boundary(t)
        dt = nb - t
        d_seg = spd * dt
        if d_seg >= rem:
            t += rem / spd
            rem = 0
        else:
            t = nb
            rem -= d_seg
    return t - depart_t


def fpk(v):
    """百公里油耗(L/100km)"""
    return 0.0025 * v * v - 0.2554 * v + 31.75


def epk(v):
    """百公里电耗(kWh/100km)"""
    return 0.0014 * v * v - 0.12 * v + 36.19


def segment_energy(dist, depart_t, is_ev, load_ratio):
    """
    计算一段路程的能源成本和碳排放
    返回: (能源费用, 碳排放费用)
    """
    if dist < 1e-9:
        return 0.0, 0.0

    # 分段计算(跨时段)
    rem = dist
    t = depart_t
    total_energy_cost = 0.0
    total_carbon_cost = 0.0

    for _ in range(50):
        if rem < 1e-9:
            break
        spd = get_speed(t)
        if spd < 0.5:
            spd = 0.5
        nb = _next_boundary(t)
        dt = nb - t
        d_seg = min(spd * dt, rem)

        if is_ev:
            cons = epk(spd) * (1 + load_ratio * EV_LOAD_EXTRA) * d_seg / 100.0
            total_energy_cost += cons * ELEC_PRICE
            total_carbon_cost += cons * GAMMA_ELEC * CARBON_PRICE
        else:
            cons = fpk(spd) * (1 + load_ratio * FUEL_LOAD_EXTRA) * d_seg / 100.0
            total_energy_cost += cons * FUEL_PRICE
            total_carbon_cost += cons * ETA_FUEL * CARBON_PRICE

        if spd * dt >= rem:
            rem = 0
        else:
            t = nb
            rem -= d_seg

    return total_energy_cost, total_carbon_cost


def route_cost_detail(route_nodes, dist_mat, nodes, vtype):
    """
    计算一条路径的详细成本
    route_nodes: [c1, c2, ...] 客户索引(不含仓库)
    返回: dict with cost breakdown and timing info
    """
    if not route_nodes:
        return None

    is_ev = vtype["is_ev"]
    cap_w = vtype["cap_w"]
    total_w = sum(nodes[c]["weight"] for c in route_nodes)
    total_v = sum(nodes[c]["volume"] for c in route_nodes)

    energy_cost = 0.0
    carbon_cost = 0.0
    wait_cost = 0.0
    late_cost = 0.0
    arrivals = []
    departures = []

    t = EARLIEST_DEPART
    current_load_w = total_w
    prev = 0  # depot

    for i, c in enumerate(route_nodes):
        d = dist_mat[prev][c]
        lr = current_load_w / cap_w if cap_w > 0 else 0
        lr = min(lr, 1.0)

        tt = travel_time(d, t)
        arrive = t + tt

        ec, cc = segment_energy(d, t, is_ev, lr)
        energy_cost += ec
        carbon_cost += cc

        # 时间窗处理
        tw_s = nodes[c]["tw_start"]
        tw_e = nodes[c]["tw_end"]

        if arrive < tw_s:
            wait_cost += (tw_s - arrive) * WAIT_COST_RATE
            arrive = tw_s  # 等到时间窗开始
        elif arrive > tw_e:
            late_cost += (arrive - tw_e) * LATE_COST_RATE

        arrivals.append(arrive)
        depart = arrive + SERVICE_TIME
        departures.append(depart)

        current_load_w -= nodes[c]["weight"]
        prev = c
        t = depart

    # 返回仓库
    d = dist_mat[prev][0]
    lr = 0.0  # 空载返回
    tt = travel_time(d, t)
    ec, cc = segment_energy(d, t, is_ev, lr)
    energy_cost += ec
    carbon_cost += cc

    return {
        "start_cost": START_COST,
        "energy_cost": energy_cost,
        "carbon_cost": carbon_cost,
        "wait_cost": wait_cost,
        "late_cost": late_cost,
        "total": START_COST + energy_cost + carbon_cost + wait_cost + late_cost,
        "arrivals": arrivals,
        "departures": departures,
        "total_w": total_w,
        "total_v": total_v,
    }
