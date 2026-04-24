"""ALNS求解器模块 - 优化版"""
import random
import math
import numpy as np
from vrp_config import *
from vrp_utils import route_cost_detail


class Solution:
    def __init__(self):
        self.routes = []  # [(vtype_idx, [customer_indices]), ...]
        self.cost = float("inf")
        self.unassigned = set()

    def deep_copy(self):
        s = Solution()
        s.routes = [(vt, list(cs)) for vt, cs in self.routes]
        s.cost = self.cost
        s.unassigned = set(self.unassigned)
        return s


def eval_solution(sol, dist_mat, nodes):
    total = 0.0
    for vt_idx, custs in sol.routes:
        if not custs:
            continue
        info = route_cost_detail(custs, dist_mat, nodes, VEHICLE_TYPES[vt_idx])
        if info:
            total += info["total"]
    total += len(sol.unassigned) * 100000
    sol.cost = total
    return total


def fast_insert_cost(custs, pos, c, dist_mat):
    """快速插入成本估算(仅距离增量)"""
    if not custs:
        return dist_mat[0][c] + dist_mat[c][0]
    if pos == 0:
        return dist_mat[0][c] + dist_mat[c][custs[0]] - dist_mat[0][custs[0]]
    if pos == len(custs):
        return dist_mat[custs[-1]][c] + dist_mat[c][0] - dist_mat[custs[-1]][0]
    prev, nxt = custs[pos - 1], custs[pos]
    return dist_mat[prev][c] + dist_mat[c][nxt] - dist_mat[prev][nxt]


def count_vehicles(sol):
    counts = [0] * len(VEHICLE_TYPES)
    for vt_idx, custs in sol.routes:
        if custs:
            counts[vt_idx] += 1
    return counts


def pick_vehicle(used, w=0, v=0):
    best, best_s = None, float("inf")
    for i, vt in enumerate(VEHICLE_TYPES):
        if used[i] >= vt["count"]:
            continue
        if vt["cap_w"] >= w - 1e-6 and vt["cap_v"] >= v - 1e-6:
            s = vt["cap_w"] + vt["cap_v"] * 200
            if s < best_s:
                best_s, best = s, i
    if best is None:
        for i, vt in enumerate(VEHICLE_TYPES):
            if used[i] < vt["count"]:
                return i
    return best


# ======================================================================
# 初始解 - 快速贪心
# ======================================================================
def build_initial_solution(nodes, dist_mat):
    sol = Solution()
    customers = sorted(range(1, len(nodes)), key=lambda c: nodes[c]["tw_start"])
    unserved = list(customers)
    used = [0] * len(VEHICLE_TYPES)

    while unserved:
        seed = unserved[0]
        vt_idx = pick_vehicle(used, nodes[seed]["weight"], nodes[seed]["volume"])
        if vt_idx is None:
            for c in unserved:
                sol.unassigned.add(c)
            break

        vt = VEHICLE_TYPES[vt_idx]
        route = [seed]
        unserved.remove(seed)
        used[vt_idx] += 1
        cur_w = nodes[seed]["weight"]
        cur_v = nodes[seed]["volume"]

        # 贪心插入邻近客户
        changed = True
        while changed:
            changed = False
            best_cost, best_c, best_p = float("inf"), None, None
            for c in unserved:
                if cur_w + nodes[c]["weight"] > vt["cap_w"] + 1e-6:
                    continue
                if cur_v + nodes[c]["volume"] > vt["cap_v"] + 1e-6:
                    continue
                for pos in range(len(route) + 1):
                    d = fast_insert_cost(route, pos, c, dist_mat)
                    if d < best_cost:
                        best_cost, best_c, best_p = d, c, pos
            if best_c is not None:
                route.insert(best_p, best_c)
                unserved.remove(best_c)
                cur_w += nodes[best_c]["weight"]
                cur_v += nodes[best_c]["volume"]
                changed = True

        sol.routes.append((vt_idx, route))

    eval_solution(sol, dist_mat, nodes)
    print(f"初始解: {len(sol.routes)}条路径, 成本={sol.cost:.2f}, 未分配={len(sol.unassigned)}")
    return sol


# ======================================================================
# 破坏算子
# ======================================================================
def random_removal(sol, num, nodes, dist_mat):
    pool = [(ri, c) for ri, (_, cs) in enumerate(sol.routes) for c in cs]
    if not pool:
        return []
    sel = random.sample(pool, min(num, len(pool)))
    removed = []
    for ri, c in sel:
        if c in sol.routes[ri][1]:
            sol.routes[ri][1].remove(c)
            removed.append(c)
    return removed


def worst_removal(sol, num, nodes, dist_mat):
    costs = []
    for ri, (vt_idx, cs) in enumerate(sol.routes):
        for ci, c in enumerate(cs):
            # 估算移除节省
            if len(cs) == 1:
                saving = dist_mat[0][c] * 2 + START_COST
            else:
                prev_n = 0 if ci == 0 else cs[ci - 1]
                next_n = 0 if ci == len(cs) - 1 else cs[ci + 1]
                saving = dist_mat[prev_n][c] + dist_mat[c][next_n] - dist_mat[prev_n][next_n]
            costs.append((saving, ri, c))
    costs.sort(reverse=True)
    removed = []
    for i in range(min(num, len(costs))):
        _, ri, c = costs[i]
        if c in sol.routes[ri][1]:
            sol.routes[ri][1].remove(c)
            removed.append(c)
    return removed


def shaw_removal(sol, num, nodes, dist_mat):
    pool = [c for _, cs in sol.routes for c in cs]
    if not pool:
        return []
    seed = random.choice(pool)
    sims = [(dist_mat[seed][c] + abs(nodes[seed]["tw_start"] - nodes[c]["tw_start"]) * 5, c)
            for c in pool if c != seed]
    sims.sort()
    to_rem = {seed}
    for _, c in sims[:num - 1]:
        to_rem.add(c)
    removed = []
    for ri, (_, cs) in enumerate(sol.routes):
        for c in list(cs):
            if c in to_rem:
                cs.remove(c)
                removed.append(c)
    return removed


# ======================================================================
# 修复算子
# ======================================================================
def greedy_repair(sol, removed, nodes, dist_mat):
    random.shuffle(removed)
    used = count_vehicles(sol)
    for c in removed:
        best_d, best_ri, best_p = float("inf"), None, None
        for ri, (vt_idx, cs) in enumerate(sol.routes):
            vt = VEHICLE_TYPES[vt_idx]
            tw = sum(nodes[x]["weight"] for x in cs) + nodes[c]["weight"]
            tv = sum(nodes[x]["volume"] for x in cs) + nodes[c]["volume"]
            if tw > vt["cap_w"] + 1e-6 or tv > vt["cap_v"] + 1e-6:
                continue
            for pos in range(len(cs) + 1):
                d = fast_insert_cost(cs, pos, c, dist_mat)
                if d < best_d:
                    best_d, best_ri, best_p = d, ri, pos

        new_d = dist_mat[0][c] * 2
        if new_d + START_COST * 0.1 < best_d or best_ri is None:
            vt_idx = pick_vehicle(used, nodes[c]["weight"], nodes[c]["volume"])
            if vt_idx is not None:
                sol.routes.append((vt_idx, [c]))
                used[vt_idx] += 1
                continue
        if best_ri is not None:
            sol.routes[best_ri][1].insert(best_p, c)
        else:
            vt_idx = pick_vehicle(used)
            if vt_idx is not None:
                sol.routes.append((vt_idx, [c]))
                used[vt_idx] += 1
            else:
                sol.unassigned.add(c)


def regret_repair(sol, removed, nodes, dist_mat):
    used = count_vehicles(sol)
    pool = list(removed)
    while pool:
        best_regret, best_c, best_ri, best_p, best_new_vt = -1e18, None, None, None, None
        for c in pool:
            opts = []
            for ri, (vt_idx, cs) in enumerate(sol.routes):
                vt = VEHICLE_TYPES[vt_idx]
                tw = sum(nodes[x]["weight"] for x in cs) + nodes[c]["weight"]
                tv = sum(nodes[x]["volume"] for x in cs) + nodes[c]["volume"]
                if tw > vt["cap_w"] + 1e-6 or tv > vt["cap_v"] + 1e-6:
                    continue
                for pos in range(len(cs) + 1):
                    d = fast_insert_cost(cs, pos, c, dist_mat)
                    opts.append((d, ri, pos))
            vt_new = pick_vehicle(used, nodes[c]["weight"], nodes[c]["volume"])
            if vt_new is not None:
                opts.append((dist_mat[0][c] * 2 + START_COST * 0.3, -1, 0))
            if not opts:
                continue
            opts.sort()
            regret = opts[1][0] - opts[0][0] if len(opts) >= 2 else 1e6
            if regret > best_regret:
                best_regret = regret
                best_c, best_ri, best_p = c, opts[0][1], opts[0][2]
                best_new_vt = vt_new
        if best_c is None:
            for c in pool:
                sol.unassigned.add(c)
            break
        pool.remove(best_c)
        if best_ri == -1:
            sol.routes.append((best_new_vt, [best_c]))
            used[best_new_vt] += 1
        else:
            sol.routes[best_ri][1].insert(best_p, best_c)


# ======================================================================
# ALNS主循环
# ======================================================================
def alns_solve(nodes, dist_mat):
    random.seed(SEED)
    np.random.seed(SEED)
    n_cust = len(nodes) - 1
    print(f"\n开始ALNS求解, 客户节点数={n_cust}")

    sol = build_initial_solution(nodes, dist_mat)
    best = sol.deep_copy()

    d_ops = [random_removal, worst_removal, shaw_removal]
    r_ops = [greedy_repair, regret_repair]
    nd, nr = len(d_ops), len(r_ops)
    dw = [1.0] * nd
    rw = [1.0] * nr
    ds = [0.0] * nd
    rs = [0.0] * nr
    du = [0] * nd
    ru = [0] * nr

    T = max(best.cost * ALNS_TEMP_FACTOR, 1000)

    for it in range(ALNS_ITER):
        di = random.choices(range(nd), weights=dw)[0]
        ri = random.choices(range(nr), weights=rw)[0]
        num = random.randint(max(1, int(n_cust * ALNS_REM_MIN)),
                             max(2, int(n_cust * ALNS_REM_MAX)))

        ns = sol.deep_copy()
        rem = d_ops[di](ns, num, nodes, dist_mat)
        r_ops[ri](ns, rem, nodes, dist_mat)
        ns.routes = [(vt, cs) for vt, cs in ns.routes if cs]
        eval_solution(ns, dist_mat, nodes)

        du[di] += 1
        ru[ri] += 1
        delta = ns.cost - sol.cost

        if ns.cost < best.cost - 1e-6:
            best = ns.deep_copy()
            sol = ns
            ds[di] += ALNS_S1
            rs[ri] += ALNS_S1
        elif ns.cost < sol.cost - 1e-6:
            sol = ns
            ds[di] += ALNS_S2
            rs[ri] += ALNS_S2
        elif delta < 1e-6 or (T > 1e-9 and random.random() < math.exp(-max(delta, 0) / T)):
            sol = ns
            ds[di] += ALNS_S3
            rs[ri] += ALNS_S3

        T *= ALNS_COOL

        if (it + 1) % ALNS_SEG == 0:
            for i in range(nd):
                if du[i] > 0:
                    dw[i] = dw[i] * ALNS_DECAY + (1 - ALNS_DECAY) * ds[i] / du[i]
                ds[i] = du[i] = 0
            for i in range(nr):
                if ru[i] > 0:
                    rw[i] = rw[i] * ALNS_DECAY + (1 - ALNS_DECAY) * rs[i] / ru[i]
                rs[i] = ru[i] = 0

        if (it + 1) % 500 == 0:
            print(f"  迭代 {it+1}/{ALNS_ITER}: 当前={sol.cost:.2f}, 最优={best.cost:.2f}, T={T:.1f}")

    print(f"\nALNS完成! 最优成本={best.cost:.2f}")
    return best
