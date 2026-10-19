import time
from itertools import product
import pandas as pd
import streamlit as st
from qiskit.primitives import StatevectorSampler
from qiskit_algorithms import QAOA
from qiskit_algorithms.optimizers import COBYLA
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.algorithms import MinimumEigenOptimizer

st.title("⚡ Q-RESTORE")
st.caption("Quantum-assisted emergency power restoration")

capacity = st.number_input("Battery capacity (units)", 1, 100, 10)
df = st.data_editor(
    pd.DataFrame({
        "Load": ["Hospital", "Cell Tower", "Water Pump", "Shelter"],
        "Demand": [6, 5, 5, 4],
        "Priority": [7, 5, 5, 1],
    }),
    num_rows="dynamic",
)
loads = [(r.Load, int(r.Demand), int(r.Priority))
         for r in df.dropna().itertuples() if r.Demand > 0]

def brute_force(loads, cap):
    best, best_p = [0] * len(loads), 0
    for ch in product([0, 1], repeat=len(loads)):
        d = sum(c * l[1] for c, l in zip(ch, loads))
        p = sum(c * l[2] for c, l in zip(ch, loads))
        if d <= cap and p > best_p:
            best, best_p = list(ch), p
    return best, best_p

def greedy(loads, cap):
    order = sorted(range(len(loads)), key=lambda i: loads[i][2] / loads[i][1], reverse=True)
    ch, used = [0] * len(loads), 0
    for i in order:
        if used + loads[i][1] <= cap:
            ch[i], used = 1, used + loads[i][1]
    return ch, sum(c * l[2] for c, l in zip(ch, loads))

def run_qaoa(loads, cap):
    qp = QuadraticProgram("Q-RESTORE")
    for i in range(len(loads)):
        qp.binary_var(name=f"x{i}")
    qp.maximize(linear={f"x{i}": loads[i][2] for i in range(len(loads))})
    qp.linear_constraint(
        linear={f"x{i}": loads[i][1] for i in range(len(loads))},
        sense="<=", rhs=cap, name="battery")
    qaoa = QAOA(sampler=StatevectorSampler(), optimizer=COBYLA(maxiter=50), reps=1)
    r = MinimumEigenOptimizer(qaoa).solve(qp)
    return [int(v) for v in r.x], float(r.fval)

if st.button("Restore power"):
    if not loads:
        st.warning("Add at least one load.")
        st.stop()
    rows = []
    for name, fn in [("Brute force", brute_force), ("Greedy", greedy)]:
        t = time.time(); ch, p = fn(loads, capacity)
        rows.append((name, ch, p, round(time.time() - t, 3)))
    if len(loads) <= 6:
        with st.spinner("Running QAOA on the quantum simulator..."):
            t = time.time(); ch, p = run_qaoa(loads, capacity)
            rows.append(("QAOA", ch, p, round(time.time() - t, 1)))
    else:
        st.info("QAOA is limited to 6 loads in this demo (simulator speed).")

    res = pd.DataFrame(rows, columns=["Method", "Choice", "Priority", "Time (s)"])
    res["Choice"] = res["Choice"].astype(str)
    st.dataframe(res, hide_index=True)
    st.bar_chart(res.set_index("Method")["Priority"])
    best = rows[0][1]
    st.success("Powered loads (optimal): " + ", ".join(
        l[0] for c, l in zip(best, loads) if c == 1))
