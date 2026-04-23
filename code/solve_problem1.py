from __future__ import annotations
import argparse
import copy
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
START_MIN = 8 * 60
SERVICE_MIN = 20.0
WAIT_YUAN_PER_H = 20.0
LATE_YUAN_PER_H = 50.0
FIXED_COST = 400.0

FUEL_PRICE = 7.61
ELEC_PRICE = 1.64
FUEL_CO2 = 2.547
ELEC_CO2 = 0.501
CARBON_PRICE = 0.65
FUEL_FULL_UP = 0.40
EV_FULL_UP = 0.35

# A route may use large/medium/small design capacity.
DESIGN_W = 3000.0
DESIGN_V = 13.5

# A split delivery unit is kept feasible for the smallest fuel vehicle, so the
# instance remains feasible after all large vehicles have been used.
UNIT_W = 1250.0
UNIT_V = 6.5


@dataclass(frozen=True)
class VehicleType:
    code: str
    name: str
    energy: str
    max_w: float
    max_v: float
    count: int


@dataclass(frozen=True)
class Unit:
    uid: int
    customer: int
    w: float
    v: float
    orders: float
    tw_s: float
    tw_e: float


@dataclass
class StopLoad:
    w: float = 0.0
    v: float = 0.0
    orders: float = 0.0
    unit_ids: List[int] = field(default_factory=list)


@dataclass
class Route:
    seq: List[int] = field(default_factory=list)
    loads: Dict[int, StopLoad] = field(default_factory=dict)
    w: float = 0.0
    v: float = 0.0
    cost: float = 0.0
    cap_w: float = DESIGN_W
    cap_v: float = DESIGN_V
    design_group: str = "large"

    def add(self, unit: Unit, pos: Optional[int] = None) -> None:
        if unit.customer not in self.loads:
            if pos is None:
                self.seq.append(unit.customer)
            else:
                self.seq.insert(pos, unit.customer)
            self.loads[unit.customer] = StopLoad()
        load = self.loads[unit.customer]
        load.w += unit.w
        load.v += unit.v
        load.orders += unit.orders
        load.unit_ids.append(unit.uid)
        self.w += unit.w
        self.v += unit.v


VEHICLES = [
    VehicleType("F3000", "燃油车-3000kg/13.5m3", "fuel", 3000.0, 13.5, 60),
    VehicleType("F1500", "燃油车-1500kg/10.8m3", "fuel", 1500.0, 10.8, 50),
    VehicleType("F1250", "燃油车-1250kg/6.5m3", "fuel", 1250.0, 6.5, 50),
    VehicleType("E3000", "新能源车-3000kg/15m3", "ev", 3000.0, 15.0, 10),
    VehicleType("E1250", "新能源车-1250kg/8.5m3", "ev", 1250.0, 8.5, 15),
]


# The statement only gives 8:00-17:00. Later windows are set to "general" speed.
SPEEDS = [
    (0, 8 * 60, 35.4),
    (8 * 60, 9 * 60, 9.8),
    (9 * 60, 10 * 60, 55.3),
    (10 * 60, int(11.5 * 60), 35.4),
    (int(11.5 * 60), 13 * 60, 9.8),
    (13 * 60, 15 * 60, 55.3),
    (15 * 60, 24 * 60, 35.4),
]


def parse_hhmm(x) -> float:
    if hasattr(x, "hour") and hasattr(x, "minute"):
        return float(x.hour * 60 + x.minute)
    text = str(x).strip().split()[-1]
    h, m = text.split(":")[:2]
    return float(int(h) * 60 + int(m))


def fmt_time(x: float) -> str:
    total = int(round(x))
    day, minute = divmod(total, 24 * 60)
    h, m = divmod(minute, 60)
    return f"+{day}d {h:02d}:{m:02d}" if day else f"{h:02d}:{m:02d}"


def speed_at(t: float) -> float:
    minute = t % (24 * 60)
    for s, e, v in SPEEDS:
        if s <= minute < e:
            return v
    return 35.4


def next_boundary(t: float) -> float:
    day = math.floor(t / (24 * 60))
    minute = t - day * 24 * 60
    for b in sorted({e for _, e, _ in SPEEDS}):
        if b > minute + 1e-9:
            return day * 24 * 60 + b
    return (day + 1) * 24 * 60


def travel_parts(km: float, depart: float) -> List[Tuple[float, float, float]]:
    left, t, out = float(km), float(depart), []
    while left > 1e-9:
        v = speed_at(t)
        dt = max(next_boundary(t) - t, 1e-6)
        can = v * dt / 60.0
        if left <= can + 1e-9:
            used = left / v * 60.0
            out.append((left, v, used))
            break
        out.append((can, v, dt))
        left -= can
        t += dt
    return out


def fpk(v: float) -> float:
    return 0.0025 * v * v - 0.2554 * v + 31.75


def epk(v: float) -> float:
    return 0.0014 * v * v - 0.12 * v + 36.19


def feasible_design(route: Route, unit: Optional[Unit] = None) -> bool:
    w = route.w + (unit.w if unit else 0.0)
    v = route.v + (unit.v if unit else 0.0)
    return w <= route.cap_w + 1e-7 and v <= route.cap_v + 1e-7


def feasible_vehicle(route: Route, veh: VehicleType) -> bool:
    return route.w <= veh.max_w + 1e-7 and route.v <= veh.max_v + 1e-7


def depart_guess(route: Route, dist: np.ndarray, tw: Dict[int, Tuple[float, float]]) -> float:
    if not route.seq:
        return START_MIN
    first = route.seq[0]
    return max(START_MIN, tw[first][0] - dist[0, first] / 35.4 * 60.0)


def load_mult(route: Route, veh: VehicleType, remain_w: float, remain_v: float) -> float:
    ratio = max(remain_w / veh.max_w, remain_v / veh.max_v, 0.0)
    ratio = min(1.0, ratio)
    return 1.0 + ratio * (FUEL_FULL_UP if veh.energy == "fuel" else EV_FULL_UP)


def eval_route(
    route: Route,
    veh: VehicleType,
    dist: np.ndarray,
    tw: Dict[int, Tuple[float, float]],
    depart: Optional[float] = None,
) -> Dict:
    if depart is None:
        depart = depart_guess(route, dist, tw)

    t = float(depart)
    node = 0
    remain_w, remain_v = route.w, route.v
    fixed = FIXED_COST if route.seq else 0.0
    energy_cost = carbon_cost = wait_cost = late_cost = 0.0
    fuel_l = elec_kwh = carbon_kg = distance = 0.0
    stops = []

    for idx, cust in enumerate(route.seq, 1):
        leg = float(dist[node, cust])
        mult = load_mult(route, veh, remain_w, remain_v)
        for seg_km, speed, seg_min in travel_parts(leg, t):
            distance += seg_km
            if veh.energy == "fuel":
                used = seg_km / 100.0 * fpk(speed) * mult
                fuel_l += used
                energy_cost += used * FUEL_PRICE
                co2 = used * FUEL_CO2
            else:
                used = seg_km / 100.0 * epk(speed) * mult
                elec_kwh += used
                energy_cost += used * ELEC_PRICE
                co2 = used * ELEC_CO2
            carbon_kg += co2
            carbon_cost += co2 * CARBON_PRICE
            t += seg_min

        arrival = t
        s, e = tw[cust]
        wait = max(0.0, s - arrival)
        late = max(0.0, arrival - e)
        wait_cost += wait / 60.0 * WAIT_YUAN_PER_H
        late_cost += late / 60.0 * LATE_YUAN_PER_H
        service_start = max(arrival, s)
        depart_stop = service_start + SERVICE_MIN
        load = route.loads[cust]
        stops.append(
            {
                "stop_index": idx,
                "customer_id": cust,
                "arrival_min": arrival,
                "service_start_min": service_start,
                "depart_min": depart_stop,
                "tw_start_min": s,
                "tw_end_min": e,
                "wait_min": wait,
                "late_min": late,
                "delivered_weight": load.w,
                "delivered_volume": load.v,
                "order_count": load.orders,
                "unit_ids": ",".join(map(str, load.unit_ids)),
            }
        )
        t = depart_stop
        remain_w -= load.w
        remain_v -= load.v
        node = cust

    if route.seq:
        leg = float(dist[node, 0])
        mult = load_mult(route, veh, remain_w, remain_v)
        for seg_km, speed, seg_min in travel_parts(leg, t):
            distance += seg_km
            if veh.energy == "fuel":
                used = seg_km / 100.0 * fpk(speed) * mult
                fuel_l += used
                energy_cost += used * FUEL_PRICE
                co2 = used * FUEL_CO2
            else:
                used = seg_km / 100.0 * epk(speed) * mult
                elec_kwh += used
                energy_cost += used * ELEC_PRICE
                co2 = used * ELEC_CO2
            carbon_kg += co2
            carbon_cost += co2 * CARBON_PRICE
            t += seg_min

    total = fixed + energy_cost + carbon_cost + wait_cost + late_cost
    return {
        "total_cost": total,
        "fixed_cost": fixed,
        "energy_cost": energy_cost,
        "carbon_cost": carbon_cost,
        "wait_cost": wait_cost,
        "late_cost": late_cost,
        "distance_km": distance,
        "fuel_liter": fuel_l,
        "electricity_kwh": elec_kwh,
        "carbon_kg": carbon_kg,
        "depart_min": float(depart),
        "return_min": t,
        "stops": stops,
    }


def best_depart(route: Route, veh: VehicleType, dist: np.ndarray, tw: Dict[int, Tuple[float, float]]) -> Dict:
    if not route.seq:
        return eval_route(route, veh, dist, tw, START_MIN)
    first = route.seq[0]
    candidates = set(range(START_MIN, 22 * 60 + 1, 10))
    for cust in route.seq:
        s, e = tw[cust]
        travel = dist[0, first] / 35.4 * 60.0
        candidates.update([round(s), round(e), round(s - travel), round(e - travel)])
    best = None
    for d in sorted(x for x in candidates if START_MIN <= x <= 22 * 60):
        cur = eval_route(route, veh, dist, tw, float(d))
        if best is None or cur["total_cost"] < best["total_cost"]:
            best = cur
    return best


def clone_add(route: Route, unit: Unit, pos: Optional[int]) -> Route:
    cand = copy.deepcopy(route)
    cand.add(unit, pos)
    return cand


def build_routes(units: List[Unit], dist: np.ndarray, tw: Dict[int, Tuple[float, float]]) -> List[Route]:
    build_veh = next(v for v in VEHICLES if v.code == "F3000")
    routes: List[Route] = []
    slots = (
        [("large", 3000.0, 13.5)] * 70
        + [("medium", 1500.0, 10.8)] * 50
        + [("small", 1250.0, 6.5)] * 65
    )
    next_slot = 0

    for unit in units:
        single_probe = Route(cap_w=UNIT_W, cap_v=UNIT_V, design_group="probe")
        single_probe.add(unit)
        single_cost = eval_route(single_probe, build_veh, dist, tw)["total_cost"]
        best_i, best_cand, best_delta = None, None, math.inf

        for i, route in enumerate(routes):
            if not feasible_design(route, unit):
                continue
            positions = [None] if unit.customer in route.loads else range(len(route.seq) + 1)
            for pos in positions:
                cand = clone_add(route, unit, pos)
                cand.cost = eval_route(cand, build_veh, dist, tw)["total_cost"]
                delta = cand.cost - route.cost
                if delta < best_delta:
                    best_i, best_cand, best_delta = i, cand, delta

        if best_cand is not None and best_delta < single_cost:
            routes[best_i] = best_cand
        else:
            while next_slot < len(slots):
                group, cap_w, cap_v = slots[next_slot]
                next_slot += 1
                if unit.w <= cap_w + 1e-7 and unit.v <= cap_v + 1e-7:
                    single = Route(cap_w=cap_w, cap_v=cap_v, design_group=group)
                    single.add(unit)
                    single.cost = eval_route(single, build_veh, dist, tw)["total_cost"]
                    break
            else:
                raise RuntimeError("fleet capacity slots are exhausted")
            routes.append(single)

    return [improve_sequence(r, dist, tw, build_veh) for r in routes]


def improve_sequence(route: Route, dist: np.ndarray, tw: Dict[int, Tuple[float, float]], veh: VehicleType) -> Route:
    route = copy.deepcopy(route)
    route.cost = eval_route(route, veh, dist, tw)["total_cost"]
    if len(route.seq) <= 2:
        return route

    improved = True
    while improved:
        improved = False
        best = route
        best_cost = route.cost
        n = len(route.seq)

        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = copy.deepcopy(route)
                cand.seq[i : j + 1] = list(reversed(cand.seq[i : j + 1]))
                cand.cost = eval_route(cand, veh, dist, tw)["total_cost"]
                if cand.cost + 1e-7 < best_cost:
                    best, best_cost = cand, cand.cost

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                cand = copy.deepcopy(route)
                cust = cand.seq.pop(i)
                cand.seq.insert(j, cust)
                cand.cost = eval_route(cand, veh, dist, tw)["total_cost"]
                if cand.cost + 1e-7 < best_cost:
                    best, best_cost = cand, cand.cost

        if best_cost + 1e-7 < route.cost:
            route = best
            improved = True
    return route


def load_data(data_dir: Path):
    orders = pd.read_excel(data_dir / "订单信息.xlsx")
    tw_df = pd.read_excel(data_dir / "时间窗.xlsx")
    dist_df = pd.read_excel(data_dir / "距离矩阵.xlsx")
    coord_df = pd.read_excel(data_dir / "客户坐标信息.xlsx")

    dist = dist_df.drop(columns=["客户"]).to_numpy(dtype=float)
    tw_df["s"] = tw_df["开始时间"].map(parse_hhmm)
    tw_df["e"] = tw_df["结束时间"].map(parse_hhmm)
    tw = {int(r["客户编号"]): (float(r["s"]), float(r["e"])) for _, r in tw_df.iterrows()}

    demand = (
        orders.groupby("目标客户编号")
        .agg(weight=("重量", "sum"), volume=("体积", "sum"), orders=("订单编号", "count"))
        .reset_index()
        .rename(columns={"目标客户编号": "customer"})
    )
    coords = coord_df.set_index("ID")[["X (km)", "Y (km)"]].to_dict("index")
    depot_x, depot_y = float(coords[0]["X (km)"]), float(coords[0]["Y (km)"])

    def angle(cust: int) -> float:
        x, y = float(coords[cust]["X (km)"]), float(coords[cust]["Y (km)"])
        return math.atan2(y - depot_y, x - depot_x)

    demand["tw_s"] = demand["customer"].map(lambda c: tw[int(c)][0])
    demand["tw_e"] = demand["customer"].map(lambda c: tw[int(c)][1])
    demand["angle"] = demand["customer"].map(lambda c: angle(int(c)))
    return demand, tw, dist


def make_units(demand: pd.DataFrame) -> List[Unit]:
    units, uid = [], 1
    rows = demand.sort_values(["tw_s", "tw_e", "angle", "customer"])
    for r in rows.itertuples(index=False):
        n = int(max(1, math.ceil(r.weight / UNIT_W), math.ceil(r.volume / UNIT_V)))
        for _ in range(n):
            units.append(
                Unit(
                    uid=uid,
                    customer=int(r.customer),
                    w=float(r.weight) / n,
                    v=float(r.volume) / n,
                    orders=float(r.orders) / n,
                    tw_s=float(r.tw_s),
                    tw_e=float(r.tw_e),
                )
            )
            uid += 1
    units.sort(key=lambda x: (x.tw_s, x.tw_e, x.customer, -x.w))
    return units


def assign_vehicles(routes: List[Route], dist: np.ndarray, tw: Dict[int, Tuple[float, float]]):
    f3000 = next(v for v in VEHICLES if v.code == "F3000")
    e3000 = next(v for v in VEHICLES if v.code == "E3000")
    e1250 = next(v for v in VEHICLES if v.code == "E1250")
    remaining = {v.code: v.count for v in VEHICLES}
    assign: Dict[int, VehicleType] = {}

    savings = []
    for i, r in enumerate(routes):
        if feasible_vehicle(r, e3000):
            fuel_cost = best_depart(r, f3000, dist, tw)["total_cost"]
            ev_cost = best_depart(r, e3000, dist, tw)["total_cost"]
            savings.append((fuel_cost - ev_cost, i))

    for _, i in sorted([x for x in savings if feasible_vehicle(routes[x[1]], e1250)], reverse=True):
        if remaining["E1250"] <= 0:
            break
        assign[i] = e1250
        remaining["E1250"] -= 1

    for _, i in sorted(savings, reverse=True):
        if remaining["E3000"] <= 0:
            break
        if i not in assign:
            assign[i] = e3000
            remaining["E3000"] -= 1

    fuel_order = [
        next(v for v in VEHICLES if v.code == "F1250"),
        next(v for v in VEHICLES if v.code == "F1500"),
        next(v for v in VEHICLES if v.code == "F3000"),
    ]
    left = [i for i in range(len(routes)) if i not in assign]
    left.sort(key=lambda i: max(routes[i].w / DESIGN_W, routes[i].v / DESIGN_V), reverse=True)
    for i in left:
        chosen = None
        for veh in fuel_order:
            if remaining[veh.code] > 0 and feasible_vehicle(routes[i], veh):
                chosen = veh
                break
        if chosen is None:
            for veh in VEHICLES:
                if remaining[veh.code] > 0 and feasible_vehicle(routes[i], veh):
                    chosen = veh
                    break
        if chosen is None:
            raise RuntimeError(f"no available vehicle for route {i + 1}")
        assign[i] = chosen
        remaining[chosen.code] -= 1

    out = []
    for i, r in enumerate(routes):
        veh = assign[i]
        out.append((r, veh, best_depart(r, veh, dist, tw)))
    return out


def output_tables(assignments):
    route_rows, stop_rows = [], []
    for rid, (route, veh, ev) in enumerate(assignments, 1):
        vehicle_id = f"{veh.code}-{rid:03d}"
        route_rows.append(
            {
                "route_id": rid,
                "vehicle_id": vehicle_id,
                "vehicle_type": veh.name,
                "energy_type": veh.energy,
                "path": "0-" + "-".join(map(str, route.seq)) + "-0",
                "stop_count": len(route.seq),
                "load_weight": route.w,
                "load_volume": route.v,
                "depart_time": fmt_time(ev["depart_min"]),
                "return_time": fmt_time(ev["return_min"]),
                "distance_km": ev["distance_km"],
                "fuel_liter": ev["fuel_liter"],
                "electricity_kwh": ev["electricity_kwh"],
                "carbon_kg": ev["carbon_kg"],
                "fixed_cost": ev["fixed_cost"],
                "energy_cost": ev["energy_cost"],
                "carbon_cost": ev["carbon_cost"],
                "wait_cost": ev["wait_cost"],
                "late_cost": ev["late_cost"],
                "total_cost": ev["total_cost"],
            }
        )
        for s in ev["stops"]:
            stop_rows.append(
                {
                    "route_id": rid,
                    "vehicle_id": vehicle_id,
                    "vehicle_type": veh.name,
                    "customer_id": s["customer_id"],
                    "stop_index": s["stop_index"],
                    "arrival_time": fmt_time(s["arrival_min"]),
                    "service_start_time": fmt_time(s["service_start_min"]),
                    "depart_time": fmt_time(s["depart_min"]),
                    "time_window": f"{fmt_time(s['tw_start_min'])}-{fmt_time(s['tw_end_min'])}",
                    "wait_min": s["wait_min"],
                    "late_min": s["late_min"],
                    "delivered_weight": s["delivered_weight"],
                    "delivered_volume": s["delivered_volume"],
                    "order_count": s["order_count"],
                    "unit_ids": s["unit_ids"],
                }
            )

    route_df = pd.DataFrame(route_rows).sort_values("route_id")
    stop_df = pd.DataFrame(stop_rows).sort_values(["route_id", "stop_index"])
    cost_df = pd.DataFrame(
        [
            {
                "used_vehicles": len(route_df),
                "total_distance_km": route_df["distance_km"].sum(),
                "total_fuel_liter": route_df["fuel_liter"].sum(),
                "total_electricity_kwh": route_df["electricity_kwh"].sum(),
                "total_carbon_kg": route_df["carbon_kg"].sum(),
                "fixed_cost": route_df["fixed_cost"].sum(),
                "energy_cost": route_df["energy_cost"].sum(),
                "carbon_cost": route_df["carbon_cost"].sum(),
                "wait_cost": route_df["wait_cost"].sum(),
                "late_cost": route_df["late_cost"].sum(),
                "total_cost": route_df["total_cost"].sum(),
            }
        ]
    )
    usage_df = (
        route_df.groupby(["vehicle_type", "energy_type"])
        .agg(
            used_vehicles=("route_id", "count"),
            distance_km=("distance_km", "sum"),
            load_weight=("load_weight", "sum"),
            load_volume=("load_volume", "sum"),
            carbon_kg=("carbon_kg", "sum"),
            total_cost=("total_cost", "sum"),
        )
        .reset_index()
    )
    return route_df, stop_df, cost_df, usage_df


def solve(data_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    demand, tw, dist = load_data(data_dir)
    units = make_units(demand)
    routes = build_routes(units, dist, tw)
    assignments = assign_vehicles(routes, dist, tw)
    route_df, stop_df, cost_df, usage_df = output_tables(assignments)

    route_df.to_csv(output_dir / "problem1_vehicle_plan.csv", index=False, encoding="utf-8-sig")
    stop_df.to_csv(output_dir / "problem1_stop_times.csv", index=False, encoding="utf-8-sig")
    cost_df.to_csv(output_dir / "problem1_cost_summary.csv", index=False, encoding="utf-8-sig")
    usage_df.to_csv(output_dir / "problem1_vehicle_usage.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(output_dir / "problem1_result.xlsx", engine="openpyxl") as writer:
        cost_df.to_excel(writer, sheet_name="成本汇总", index=False)
        usage_df.to_excel(writer, sheet_name="车型使用", index=False)
        route_df.to_excel(writer, sheet_name="车辆路径", index=False)
        stop_df.to_excel(writer, sheet_name="到达时间", index=False)

    s = cost_df.iloc[0]
    print("Problem 1 solved")
    print(f"customers with demand: {len(demand)}")
    print(f"delivery units after split: {len(units)}")
    print(f"used vehicles: {int(s['used_vehicles'])}")
    print(f"total cost: {s['total_cost']:.2f}")
    print(f"fixed / energy / carbon / wait / late: {s['fixed_cost']:.2f} / {s['energy_cost']:.2f} / {s['carbon_cost']:.2f} / {s['wait_cost']:.2f} / {s['late_cost']:.2f}")
    print(f"total carbon kg: {s['total_carbon_kg']:.2f}")
    print(f"result file: {output_dir / 'problem1_result.xlsx'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=BASE_DIR / "data")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "output")
    args = parser.parse_args()
    solve(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
