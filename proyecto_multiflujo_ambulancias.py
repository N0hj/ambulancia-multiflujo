import streamlit as st
import osmnx as ox
import networkx as nx
import pulp
import folium
from streamlit_folium import st_folium
import random

st.set_page_config(layout="wide", page_title="Optimización Multiflujo de Ambulancias")

# =============================
# CONFIGURACIÓN LATERAL
# =============================
st.sidebar.header("⚙️ Configuración de parámetros")

Rmin = st.sidebar.slider("Velocidad mínima requerida (km/h)", 10, 80, 30)
Rmax = st.sidebar.slider("Velocidad máxima requerida (km/h)", 20, 120, 60)
Cmin = st.sidebar.slider("Capacidad mínima de vía (km/h)", 10, 100, 20)
Cmax = st.sidebar.slider("Capacidad máxima de vía (km/h)", 20, 150, 80)

st.sidebar.header("💰 Costos operativos de ambulancias")
costos = {
    "Leve": st.sidebar.number_input("Transporte simple (Leve)", 50, 1000, 100),
    "Media": st.sidebar.number_input("Cuidados intermedios (Media)", 50, 1000, 200),
    "Crítica": st.sidebar.number_input("Cuidados críticos (Crítica)", 50, 1000, 300)
}

if "capacidades" not in st.session_state:
    st.session_state.capacidades = {}
if "resultados" not in st.session_state:
    st.session_state.resultados = {}

# =============================
# MAPA BASE
# =============================
st.title("🚑 Optimización de rutas de ambulancias (Modelo Multiflujo con PuLP)")

# Cargar red vial real
lat, lon = 6.2442, -75.5812  # Medellín, ejemplo
G = ox.graph_from_point((lat, lon), dist=500, network_type='drive')

# Asignar velocidades aleatorias dentro del rango
for u, v, k, data in G.edges(keys=True, data=True):
    data["velocidad"] = random.uniform(Cmin, Cmax)
    data["tiempo"] = data["length"] / (data["velocidad"] * 1000 / 3600)  # segundos aprox

# =============================
# NODOS BASE Y DESTINOS
# =============================
nodos = list(G.nodes())
origen = random.choice(nodos)
destinos = random.sample(nodos, 3)

# =============================
# MODELO PULP
# =============================
def optimizar_rutas(G, origen, destinos, costos):
    prob = pulp.LpProblem("RuteoAmbulancias", pulp.LpMinimize)
    x = {}

    tipos = ["Leve", "Media", "Crítica"]
    velocidades_requeridas = {
        "Leve": random.uniform(Rmin, Rmax),
        "Media": random.uniform(Rmin, Rmax),
        "Crítica": random.uniform(Rmin, Rmax)
    }

    # Variables binarias por arista y flujo
    for u, v, k, data in G.edges(keys=True, data=True):
        for e in tipos:
            x[(u, v, k, e)] = pulp.LpVariable(f"x_{u}_{v}_{k}_{e}", cat="Binary")

    # Función objetivo
    prob += pulp.lpSum(
        x[(u, v, k, e)] * data["tiempo"] * costos[e]
        for u, v, k, data in G.edges(keys=True, data=True)
        for e in tipos
    )

    # Restricciones de capacidad y flujo
    for u, v, k, data in G.edges(keys=True, data=True):
        for e in tipos:
            prob += data["velocidad"] >= velocidades_requeridas[e] * x[(u, v, k, e)]

    for e, dest in zip(tipos, destinos):
        for n in G.nodes():
            in_edges = [(u, v, k) for u, v, k in G.in_edges(n, keys=True)]
            out_edges = [(u, v, k) for u, v, k in G.out_edges(n, keys=True)]
            prob += (
                pulp.lpSum(x[(u, v, k, e)] for u, v, k in out_edges) -
                pulp.lpSum(x[(u, v, k, e)] for u, v, k in in_edges)
                == (1 if n == origen else -1 if n == dest else 0)
            )

    solver = pulp.PULP_CBC_CMD(msg=False)
    status = prob.solve(solver)
    return x, pulp.LpStatus[prob.status], velocidades_requeridas

# =============================
# BOTONES DE ACCIÓN
# =============================
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("♻️ Recalcular capacidades"):
        for u, v, k, data in G.edges(keys=True, data=True):
            data["velocidad"] = random.uniform(Cmin, Cmax)
        st.session_state.capacidades = { (u,v,k): data["velocidad"] for u,v,k,data in G.edges(keys=True, data=True) }
        st.success("Capacidades recalculadas")

with col3:
    if st.button("🧮 Calcular rutas óptimas"):
        with st.spinner("Ejecutando optimización..."):
            x, estado, velocidades_req = optimizar_rutas(G, origen, destinos, costos)
            st.session_state.resultados = {"x": x, "estado": estado, "vel": velocidades_req}

# =============================
# MOSTRAR RESULTADOS
# =============================
if st.session_state.resultados:
    estado = st.session_state.resultados["estado"]
    st.markdown(f"### Estado de la optimización: **{estado}**")

    # Crear mapa folium
    m = folium.Map(location=[lat, lon], zoom_start=15, tiles="cartodb positron")
    folium.Marker(location=ox.graph_to_gdfs(G, nodes=True).loc[origen][['y', 'x']], 
                  tooltip="Base de ambulancias", icon=folium.Icon(color="blue", icon="hospital")).add_to(m)

    colores = {"Leve": "green", "Media": "orange", "Crítica": "red"}
    x = st.session_state.resultados["x"]

    for (u, v, k, e), var in x.items():
        if pulp.value(var) == 1:
            u_xy = (G.nodes[u]['y'], G.nodes[u]['x'])
            v_xy = (G.nodes[v]['y'], G.nodes[v]['x'])
            folium.PolyLine(
                [u_xy, v_xy], color=colores[e], weight=5, tooltip=f"{e} ({round(G[u][v][k]['velocidad'],1)} km/h)"
            ).add_to(m)

    for e, d in zip(["Leve", "Media", "Crítica"], destinos):
        folium.Marker(location=ox.graph_to_gdfs(G, nodes=True).loc[d][['y', 'x']],
                      tooltip=f"Emergencia {e}", icon=folium.Icon(color=colores[e])).add_to(m)

    st_folium(m, width=900, height=600)
