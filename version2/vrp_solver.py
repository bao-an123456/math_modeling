"""
绿色物流车辆调度优化 - 主程序
===========================================
模型: 带软时间窗的异构车队车辆路径问题 (HFVRPTW)
算法: 自适应大邻域搜索 (ALNS)
目标: 最小化总配送成本(启动+能耗+碳排放+等待+迟到惩罚)
===========================================
"""
import os
import time as time_module
from vrp_config import VEHICLE_TYPES, SERVICE_TIME
from vrp_utils import route_cost_detail
from vrp_data import load_data
from vrp_alns import alns_solve, eval_solution, count_vehicles


def format_time(hours):
    """将小时数转为 HH:MM 格式"""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h:02d}:{m:02d}"


def print_results(sol, nodes, dist_mat):
    """输出详细结果"""
    print("\n" + "=" * 80)
    print("                     车辆调度优化结果")
    print("=" * 80)

    # 1. 车辆使用汇总
    counts = count_vehicles(sol)
    print("\n【一、车辆使用方案】")
    print(f"{'车型':<20} {'可用':>6} {'使用':>6}")
    print("-" * 36)
    total_used = 0
    for i, vt in enumerate(VEHICLE_TYPES):
        if counts[i] > 0:
            print(f"{vt['name']:<16} {vt['count']:>6} {counts[i]:>6}")
            total_used += counts[i]
    print("-" * 36)
    print(f"{'合计':<16} {'':<6} {total_used:>6}")

    # 2. 各路径详细信息
    print("\n【二、行驶路径与到达时间】")
    total_costs = {
        "start": 0, "energy": 0, "carbon": 0, "wait": 0, "late": 0, "total": 0
    }
    route_idx = 0

    for vt_idx, custs in sol.routes:
        if not custs:
            continue
        route_idx += 1
        vt = VEHICLE_TYPES[vt_idx]
        info = route_cost_detail(custs, dist_mat, nodes, vt)
        if not info:
            continue

        total_costs["start"] += info["start_cost"]
        total_costs["energy"] += info["energy_cost"]
        total_costs["carbon"] += info["carbon_cost"]
        total_costs["wait"] += info["wait_cost"]
        total_costs["late"] += info["late_cost"]
        total_costs["total"] += info["total"]

        ev_str = "新能源" if vt["is_ev"] else "燃油"
        print(f"\n路径 {route_idx} [{vt['name']}({ev_str})] "
              f"载重{info['total_w']:.1f}kg/{vt['cap_w']}kg "
              f"体积{info['total_v']:.2f}m³/{vt['cap_v']}m³")

        # 路径: 仓库 -> c1 -> c2 -> ... -> 仓库
        path_str = "0(仓库)"
        for i, c in enumerate(custs):
            oid = nodes[c]["orig_id"]
            arr = format_time(info["arrivals"][i])
            dep = format_time(info["departures"][i])
            tw_s = format_time(nodes[c]["tw_start"])
            tw_e = format_time(nodes[c]["tw_end"])
            path_str += f" → {oid}[到{arr},窗{tw_s}-{tw_e}]"
        path_str += " → 0(仓库)"
        print(f"  路径: {path_str}")
        print(f"  成本: 启动{info['start_cost']:.0f} + 能耗{info['energy_cost']:.1f} "
              f"+ 碳排{info['carbon_cost']:.1f} + 等待{info['wait_cost']:.1f} "
              f"+ 惩罚{info['late_cost']:.1f} = {info['total']:.1f}元")

    # 3. 成本汇总
    print("\n" + "=" * 80)
    print("【三、成本构成汇总】")
    print("-" * 50)
    print(f"  车辆启动成本:   {total_costs['start']:>12.2f} 元")
    print(f"  燃油/电费成本:  {total_costs['energy']:>12.2f} 元")
    print(f"  碳排放成本:     {total_costs['carbon']:>12.2f} 元")
    print(f"  等待成本:       {total_costs['wait']:>12.2f} 元")
    print(f"  迟到惩罚成本:   {total_costs['late']:>12.2f} 元")
    print("-" * 50)
    print(f"  总配送成本:     {total_costs['total']:>12.2f} 元")
    print("=" * 80)

    if sol.unassigned:
        print(f"\n⚠ 未分配客户: {sol.unassigned}")


def main():
    data_dir = os.path.dirname(os.path.abspath(__file__))
    print("加载数据...")
    nodes, dist_mat = load_data(data_dir)

    print("开始求解...")
    t0 = time_module.time()
    best = alns_solve(nodes, dist_mat)
    elapsed = time_module.time() - t0
    print(f"求解耗时: {elapsed:.1f}秒")

    print_results(best, nodes, dist_mat)


if __name__ == "__main__":
    main()
