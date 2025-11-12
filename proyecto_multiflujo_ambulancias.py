# ============================================================
# 🚑 PROYECTO: Optimización de rutas de ambulancias (Multiflujo)
# Universidad Pontificia Bolivariana - UPB
# ============================================================

import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import st_folium
import random
import pulp

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(page_title="Optimización multiflujo de ambulancias", layout="wide")
st.title("🚑 Optimización Multiflujo de Ambulancias (OSMnx + PuLP)")

# ============================================================
# PARÁMETROS CONFIGURABLES
# ============================================================
st.sidebar.header("⚙️ Configuración de parámetros")

Rmin = st.sidebar.slider("Velocidad requerida mínima (km/h)", 10, 80, 20)
Rmax = st.sidebar.slider("Velocidad requerida máxima (km/h)", 20, 120, 60)
Cmin = st.sidebar.slider("Velocidad mínima de vía (km/h)", 10, 60, 20)
Cmax = st.sidebar.slider("Velocidad máxima de vía (km/h)", 40, 120, 80)

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Costos operativos (por tipo de ambulancia)")
costos = {
    "leve": st.sidebar.number_input("Transporte simple", 50, 500, 100),
    "media": st.sidebar.number_input("Cuidados intermedios", 100, 700, 250),
    "critica": st.sidebar.number_input("Cuidados críticos", 200, 900, 400),
}

# ============================================================
# CARGA DE MAPA (Área ≈ 1 km²)
# ============================================================
@st.cache_data
def cargar_mapa():
    lat, lon = 6.2433, -75.5881  # San Joaquín, Medellín
    G = ox.graph_from_point((lat, lon), dist=560, network_type="drive")
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G

G = cargar_mapa()

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================
def asignar_capacidades(G, cmin, cmax):
    """Asigna capacidades (velocidades) aleatorias a las vías."""
    for u, v, k, data in G.edges(keys=True, data=True):
        data["capacidad"] = random.uniform(cmin, cmax)
        data["length_km"] = data["length"] / 1000
        data["tiempo"] = data["length_km"] / data["capacidad"]
    return G


def generar_emergencias(G):
    """Genera una base y tres emergencias aleatorias."""
    nodos = list(G.nodes())
    base = random.choice(nodos)
    emergencias = {
        "E1": {"nodo": random.choice(nodos), "tipo": "leve"},
        "E2": {"nodo": random.choice(nodos), "tipo": "media"},
        "E3": {"nodo": random.choice(nodos), "tipo": "critica"},
    }
    return base, emergencias


def generar_vel_requeridas(emergencias, rmin, rmax):
    """Asigna velocidad requerida a cada emergencia."""
    for e in emergencias.values():
        e["vel_requerida"] = random.uniform(rmin, rmax)
    return emergencias


# ============================================================
# ESTADO INICIAL (BASE Y EMERGENCIAS)
# ============================================================
if "base" not in st.session_state or "emergencias" not in st.session_state:
    st.session_state.base, st.session_state.emergencias = generar_emergencias(G)

# ============================================================
# BOTONES DE CONTROL
# ============================================================
col1, col2, col3 = st.sidebar.columns(3)
recal_cap = col1.button("🔄 Capacidades")
recal_ubi = col2.button("🎲 Ubicaciones")
recal_flu = col3.button("🚑 Calcular")

if recal_cap or "G" not in st.session_state:
    st.session_state.G = asignar_capacidades(G.copy(), Cmin, Cmax)

if recal_ubi:
    st.session_state.base, st.session_state.emergencias = generar_emergencias(G)

st.session_state.emergencias = generar_vel_requeridas(st.session_state.emergencias, Rmin, Rmax)

# ============================================================
# MODELO MULTIFLUJO (PuLP)
# ============================================================
def optimizar_multiflujo(G, base, emergencias, costos):
    """Modelo de optimización multiflujo usando PuLP."""
    prob = pulp.LpProblem("Optimizacion_Ambulancias", pulp.LpMinimize)

    # Variable de flujo: f[e][(u,v)]
    f = {}
    for e_id, e in emergencias.items():
        f[e_id] = pulp.LpVariable.dicts(f"f_{e_id}", G.edges(keys=False), lowBound=0, upBound=1, cat="Binary")

    # Función objetivo: minimizar costo total
    prob += pulp.lpSum(
        f[e_id][(u, v)] * G[u][v][0]["length_km"] * costos[e["tipo"]]
        for e_id, e in emergencias.items()
        for u, v in G.edges()
    )

    # Restricciones de conservación de flujo
    for e_id, e in emergencias.items():
        origen, destino = base, e["nodo"]

        for n in G.nodes():
            in_edges = [(u, v) for u, v in G.in_edges(n)]
            out_edges = [(u, v) for u, v in G.out_edges(n)]

            if n == origen:
                prob += pulp.lpSum(f[e_id][(u, v)] for u, v in out_edges) - pulp.lpSum(f[e_id][(u, v)] for u, v in in_edges) == 1
            elif n == destino:
                prob += pulp.lpSum(f[e_id][(u, v)] for u, v in in_edges) - pulp.lpSum(f[e_id][(u, v)] for u, v in out_edges) == 1
            else:
                prob += pulp.lpSum(f[e_id][(u, v)] for u, v in out_edges) - pulp.lpSum(f[e_id][(u, v)] for u, v in in_edges) == 0

    # Restricción de capacidad compartida
    for u, v in G.edges():
        prob += pulp.lpSum(f[e_id][(u, v)] for e_id in emergencias) <= 1

    # Resolver
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    rutas = []
    for e_id, e in emergencias.items():
        try:
            path = nx.shortest_path(G, base, e["nodo"], weight="length")
            distancia = nx.shortest_path_length(G, base, e["nodo"], weight="length")
        except nx.NetworkXNoPath:
            continue

        rutas.append({
            "emergencia": e_id,
            "tipo": e["tipo"],
            "vel_requerida": e["vel_requerida"],
            "distancia": distancia,
            "ruta": path,
            "costo": costos[e["tipo"]],
        })

    return rutas, pulp.LpStatus[prob.status]

# ============================================================
# EJECUTAR OPTIMIZACIÓN
# ============================================================
if recal_flu or "rutas" not in st.session_state:
    st.session_state.rutas, st.session_state.status = optimizar_multiflujo(
        st.session_state.G, st.session_state.base, st.session_state.emergencias, costos
    )
    st.success(f"Optimización completada ({st.session_state.status})")

# ============================================================
# MAPA INTERACTIVO
# ============================================================
m = folium.Map(location=[6.2433, -75.5881], zoom_start=15, tiles="cartodbpositron")

# Base
b_y, b_x = G.nodes[st.session_state.base]["y"], G.nodes[st.session_state.base]["x"]
folium.Marker([b_y, b_x], icon=folium.Icon(color="blue", icon="home"), tooltip="Base de ambulancias").add_to(m)

# Emergencias
colores = {"leve": "green", "media": "orange", "critica": "red"}

for e in st.session_state.rutas:
    tipo = e["tipo"]
    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in e["ruta"]]
    folium.PolyLine(coords, color=colores[tipo], weight=6, tooltip=f"{e['emergencia']} ({tipo})").add_to(m)
    y, x = G.nodes[e["ruta"][-1]]["y"], G.nodes[e["ruta"][-1]]["x"]
    folium.Marker([y, x], icon=folium.Icon(color=colores[tipo], icon="info-sign"), tooltip=f"{e['emergencia']}").add_to(m)

st_folium(m, width=1300, height=600)

# ============================================================
# TABLA DE RESULTADOS
# ============================================================
st.subheader("📊 Resultados de Optimización")

st.table([
    {
        "Emergencia": e["emergencia"],
        "Tipo": e["tipo"],
        "Vel. Requerida (km/h)": round(e["vel_requerida"], 2),
        "Distancia (m)": round(e["distancia"], 2),
        "Costo Operativo": e["costo"],
    }
    for e in st.session_state.rutas
])
