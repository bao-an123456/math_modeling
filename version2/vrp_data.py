"""数据加载与预处理模块"""
import os
import math
import pandas as pd
import numpy as np
from vrp_config import VEHICLE_TYPES


def load_data(data_dir):
    """加载Excel数据并预处理"""
    # 1. 客户坐标
    df_coord = pd.read_excel(os.path.join(data_dir, "客户坐标信息.xlsx"))
    # 2. 时间窗
    df_tw = pd.read_excel(os.path.join(data_dir, "时间窗.xlsx"))
    # 3. 订单
    df_order = pd.read_excel(os.path.join(data_dir, "订单信息.xlsx"))
    # 4. 距离矩阵
    df_dist = pd.read_excel(os.path.join(data_dir, "距离矩阵.xlsx"))

    # 解析距离矩阵 (99x99)
    orig_dist = df_dist.iloc[:, 1:].values.astype(float)

    # 汇总客户需求
    demand = df_order.groupby("目标客户编号").agg(
        weight=("重量", "sum"), volume=("体积", "sum"), orders=("订单编号", "count")
    ).reset_index()
    demand_dict = {
        int(r["目标客户编号"]): (r["weight"], r["volume"])
        for _, r in demand.iterrows()
    }

    # 解析时间窗
    tw_dict = {}
    for _, r in df_tw.iterrows():
        cid = int(r["客户编号"])
        ts = str(r["开始时间"]).strip()
        te = str(r["结束时间"]).strip()
        h1, m1 = map(int, ts.split(":"))
        h2, m2 = map(int, te.split(":"))
        tw_dict[cid] = (h1 + m1 / 60.0, h2 + m2 / 60.0)

    # 构造节点列表 (nodes[0]=仓库, nodes[1..]=客户/拆分客户)
    # 只包含有需求的客户
    max_cap_w = max(vt["cap_w"] for vt in VEHICLE_TYPES)
    max_cap_v = max(vt["cap_v"] for vt in VEHICLE_TYPES)

    nodes = []
    # 仓库
    depot_row = df_coord[df_coord["ID"] == 0].iloc[0]
    nodes.append({
        "id": 0, "orig_id": 0,
        "x": depot_row["X (km)"], "y": depot_row["Y (km)"],
        "weight": 0, "volume": 0,
        "tw_start": 0, "tw_end": 24,
        "is_depot": True,
    })

    # 原始ID到节点索引的映射(用于距离矩阵)
    orig_id_map = {0: [0]}  # orig_id -> list of node indices

    for _, row in df_coord.iterrows():
        cid = int(row["ID"])
        if cid == 0:
            continue
        if cid not in demand_dict:
            continue  # 跳过无需求客户

        w, v = demand_dict[cid]
        tw = tw_dict.get(cid, (8.0, 21.0))

        # 判断是否需要拆分
        n_split = max(1, math.ceil(w / max_cap_w), math.ceil(v / max_cap_v))

        for s in range(n_split):
            idx = len(nodes)
            if cid not in orig_id_map:
                orig_id_map[cid] = []
            orig_id_map[cid].append(idx)
            nodes.append({
                "id": idx, "orig_id": cid,
                "x": row["X (km)"], "y": row["Y (km)"],
                "weight": w / n_split,
                "volume": v / n_split,
                "tw_start": tw[0], "tw_end": tw[1],
                "is_depot": False,
            })

    n = len(nodes)
    print(f"节点总数: {n} (仓库1 + 客户/拆分节点{n-1})")

    # 构造扩展距离矩阵
    dist_mat = np.zeros((n, n))
    for i in range(n):
        oi = nodes[i]["orig_id"]
        for j in range(n):
            oj = nodes[j]["orig_id"]
            dist_mat[i][j] = orig_dist[oi][oj]

    return nodes, dist_mat
