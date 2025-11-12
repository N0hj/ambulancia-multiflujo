import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import st_folium
import random
import pulp

# =========================
# CONFIGURACIÓN DE PÁGINA
# =========================
st.set_page_config(page_title="Optimización de rutas de ambulancias", layout="wide")
st.title("🚑 Optimización de rutas de ambulancias - Modelo multiflujo (PuLP)")

# =========================
# SIDEBAR DE PARÁMETROS
# =========================
st.sidebar.header("⚙️ Configuración de parámetros")

Rmin = st.sidebar.slider("Velocidad mínima requerida (km/h)", 10, 100, 30)
Rmax = st.sidebar.slider("Velocidad máxima requerida (km/h)", 20, 120, 60)
Cmin = st.sidebar.slider("Capacidad mínima de vía (km/h)", 10, 100, 20)
Cmax = st.sidebar.slider("Capacidad máxima de vía (km/h)", 20, 120, 80)

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Costos operativos por tipo de ambulancia")

costos = {
    "leve": st.sidebar.number_input("Leve", min_value=50, max_value=500, value=100),
    "media": st.sidebar.number_input("Media", min_value=100, max_value=600, value=200),
    "critica": st.sidebar.number_input("Crítica", min_value=150, max_value=800, value=300)
}

# =========================
# CARGA DEL MAPA
# =========================
@st.cache_data
def cargar_mapa():
    lat, lon = 6.2433, -75.5881  # San Joaquín, Medellín
    G = ox.graph_from_point((lat, lon), dist=800, network_type="drive")
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G

G = cargar_mapa()
nodos = list(G.nodes())

# =========================
# BASE Y EMERGENCIAS
# =========================
if "base" not in st.session_state or st.sidebar.button("🎲 Recalcular ubicaciones"):
    st.session_state.base = random.choice(nodos)
    st.session_state.emergencias = {
        "E1": {"nodo": random.choice(nodos), "tipo": "leve"},
        "E2": {"nodo": random.choice(nodos), "tipo": "media"},
        "E3": {"nodo": random.choice(nodos), "tipo": "critica"}
    }

base = st.session_state.base
emergencias = st.session_state.emergencias

# =========================
# ASIGNAR CAPACIDADES
# =========================
def asignar_capacidades(G, cmin, cmax):
    for u, v, k, data in G.edges(keys=True, data=True):
        data["capacidad"] = random.uniform(cmin, cmax)
    return G

if "G" not in st.session_state or st.sidebar.button("🔄 Recalcular capacidades"):
    st.session_state.G = asignar_capacidades(G.copy(), Cmin, Cmax)

# =========================
# MODELO DE OPTIMIZACIÓN MULTIFLUJO
# =========================
def optimizar_con_pulp(G, base, emergencias, costos):
    prob = pulp.LpProblem("RuteoAmbulancias", pulp.LpMinimize)
    edges = list(G.edges())

    # Variables: x_(u,v,k)
    x = pulp.LpVariable.dicts("x", ((u, v, k) for (u, v) in edges for k in emergencias), 0, 1, pulp.LpBinary)

    # Objetivo
    prob += pulp.lpSum(G[u][v][0]['travel_time'] * costos[emergencias[k]['tipo']] * x[(u, v, k)] for (u, v) in edges for k in emergencias)

    # Restricciones de conservación de flujo
    for k, info in emergencias.items():
        nodo_em = info["nodo"]
        for n in G.nodes():
            in_edges = [(u, v) for (u, v) in edges if v == n]
            out_edges = [(u, v) for (u, v) in edges if u == n]
            if n == base:
                prob += pulp.lpSum(x[(u, v, k)] for (u, v) in out_edges) - pulp.lpSum(x[(u, v, k)] for (u, v) in in_edges) == 1
            elif n == nodo_em:
                prob += pulp.lpSum(x[(u, v, k)] for (u, v) in out_edges) - pulp.lpSum(x[(u, v, k)] for (u, v) in in_edges) == -1
            else:
                prob += pulp.lpSum(x[(u, v, k)] for (u, v) in out_edges) - pulp.lpSum(x[(u, v, k)] for (u, v) in in_edges) == 0

    # Restricción de capacidad de aristas
    for (u, v) in edges:
        prob += pulp.lpSum(x[(u, v, k)] for k in emergencias) <= 1

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    rutas = []
    for k, info in emergencias.items():
        path = [base]
        current = base
        while current != info["nodo"]:
            next_edges = [v for (u, v) in edges if pulp.value(x[(u, v, k)]) > 0.5 and u == current]
            if not next_edges:
                break
            current = next_edges[0]
            path.append(current)
        rutas.append({
            "emergencia": k,
            "tipo": info["tipo"],
            "ruta": path,
            "costo": costos[info["tipo"]],
        })
    return rutas

# =========================
# CÁLCULO DE RUTAS
# =========================
if st.sidebar.button("🚑 Calcular rutas óptimas"):
    st.session_state.rutas = optimizar_con_pulp(st.session_state.G, base, emergencias, costos)

# =========================
# VISUALIZACIÓN
# =========================
if "rutas" in st.session_state:
    m = folium.Map(location=[6.2433, -75.5881], zoom_start=15, tiles="cartodbpositron")

    # Base
    lat, lon = G.nodes[base]['y'], G.nodes[base]['x']
    folium.Marker([lat, lon], popup="Base", icon=folium.Icon(color="blue", icon="home")).add_to(m)

    # Emergencias
    colores = {"leve": "green", "media": "orange", "critica": "red"}
    for e in st.session_state.rutas:
        tipo = e["tipo"]
        path = e["ruta"]
        coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path if n in G.nodes()]
        if len(coords) > 1:
            folium.PolyLine(coords, color=colores[tipo], weight=5, tooltip=f"{e['emergencia']} ({tipo})").add_to(m)
        lat_e, lon_e = G.nodes[path[-1]]['y'], G.nodes[path[-1]]['x']
        folium.Marker([lat_e, lon_e], popup=f"{e['emergencia']} ({tipo})", icon=folium.Icon(color=colores[tipo])).add_to(m)

    st_folium(m, width=1200, height=600)
    st.subheader("📊 Resultados de Optimización")
    st.table([{"Emergencia": e["emergencia"], "Tipo": e["tipo"], "Costo": e["costo"], "Longitud ruta": len(e["ruta"])} for e in st.session_state.rutas])
