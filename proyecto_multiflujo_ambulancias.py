# ============================================================
# 🚑 PROYECTO: Optimización de rutas de ambulancias (Multiflujo con PuLP)
# Autor: [Tu Nombre]
# Universidad: [UPB]
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
st.set_page_config(page_title="Optimización de rutas de ambulancias", layout="wide")
st.title("🚑 Optimización de rutas de ambulancias - Modelo multiflujo (PuLP)")

st.sidebar.header("⚙️ Configuración de parámetros")

# ============================================================
# PARÁMETROS CONFIGURABLES
# ============================================================
Rmin = st.sidebar.slider("Velocidad mínima requerida (km/h)", 10, 100, 30)
Rmax = st.sidebar.slider("Velocidad máxima requerida (km/h)", 20, 120, 60)
Cmin = st.sidebar.slider("Capacidad mínima de vía (km/h)", 10, 100, 20)
Cmax = st.sidebar.slider("Capacidad máxima de vía (km/h)", 20, 120, 80)

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Costos operativos")

costos = {
    "leve": st.sidebar.number_input("Leve", min_value=50, max_value=500, value=100),
    "media": st.sidebar.number_input("Media", min_value=100, max_value=600, value=200),
    "critica": st.sidebar.number_input("Crítica", min_value=150, max_value=800, value=300),
}

# ============================================================
# DESCARGA Y PROCESO DE MAPA
# ============================================================
@st.cache_data
def cargar_mapa():
    lat, lon = 6.2433, -75.5881
    G = ox.graph_from_point((lat, lon), dist=800, network_type="drive")
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G

G = cargar_mapa()
nodos = list(G.nodes())

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================
def asignar_capacidades(G, cmin, cmax):
    for u, v, k, data in G.edges(keys=True, data=True):
        data["capacidad"] = random.uniform(cmin, cmax)
    return G

def generar_velocidades_requeridas(emergencias, rmin, rmax):
    for e in emergencias.values():
        e["vel_requerida"] = random.uniform(rmin, rmax)
    return emergencias

# ============================================================
# SESIÓN: BASE Y EMERGENCIAS
# ============================================================
if "base" not in st.session_state:
    st.session_state.base = random.choice(nodos)

if "emergencias" not in st.session_state:
    st.session_state.emergencias = {
        "E1": {"nodo": random.choice(nodos), "tipo": "leve"},
        "E2": {"nodo": random.choice(nodos), "tipo": "media"},
        "E3": {"nodo": random.choice(nodos), "tipo": "critica"},
    }

# ============================================================
# MODELO MULTIFLUJO (PULP)
# ============================================================
def optimizar_multiflujo(G, base, emergencias, costos):
    conectadas = {k: e for k, e in emergencias.items() if nx.has_path(G, base, e["nodo"])}

    if not conectadas:
        return [], "Infeasible (Sin rutas posibles)"

    prob = pulp.LpProblem("Ruteo_Multiflujo", pulp.LpMinimize)

    # Variables: x_(u,v,k)
    x = pulp.LpVariable.dicts(
        "x", ((u, v, key, k) for u, v, key in G.edges(keys=True) for k in conectadas), cat="Binary"
    )

    # Función objetivo
    prob += pulp.lpSum(
        G[u][v][key]["length"] * costos[conectadas[k]["tipo"]] * x[(u, v, key, k)]
        for u, v, key in G.edges(keys=True)
        for k in conectadas
    )

    # Restricciones de capacidad
    for u, v, key, data in G.edges(keys=True, data=True):
        prob += pulp.lpSum(x[(u, v, key, k)] for k in conectadas) <= 1, f"capacidad_{u}_{v}_{key}"

    # Restricciones de conservación de flujo
    for k, e in conectadas.items():
        origen, destino = base, e["nodo"]
        for n in G.nodes():
            in_edges = [(u, v, key) for u, v, key in G.in_edges(n, keys=True)]
            out_edges = [(u, v, key) for u, v, key in G.out_edges(n, keys=True)]
            if n == origen:
                prob += (
                    pulp.lpSum(x[(u, v, key, k)] for u, v, key in out_edges)
                    - pulp.lpSum(x[(u, v, key, k)] for u, v, key in in_edges)
                    == 1
                )
            elif n == destino:
                prob += (
                    pulp.lpSum(x[(u, v, key, k)] for u, v, key in in_edges)
                    - pulp.lpSum(x[(u, v, key, k)] for u, v, key in out_edges)
                    == 1
                )
            else:
                prob += (
                    pulp.lpSum(x[(u, v, key, k)] for u, v, key in out_edges)
                    - pulp.lpSum(x[(u, v, key, k)] for u, v, key in in_edges)
                    == 0
                )

    # Resolver modelo
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    estado = pulp.LpStatus[prob.status]

    # Si no es óptimo
    if estado != "Optimal":
        return [], estado

    rutas = []
    for nombre, e in conectadas.items():
        tipo = e["tipo"]
        try:
            path = nx.shortest_path(G, base, e["nodo"], weight="length")
            distancia = nx.shortest_path_length(G, base, e["nodo"], weight="length")
        except nx.NetworkXNoPath:
            continue

        rutas.append(
            {
                "emergencia": nombre,
                "tipo": tipo,
                "vel_requerida": e["vel_requerida"],
                "ruta": path,
                "distancia": distancia,
                "costo": costos[tipo],
            }
        )
    return rutas, estado

# ============================================================
# BOTONES
# ============================================================
col1, col2, col3 = st.sidebar.columns(3)
recalcular_cap = col1.button("🔄 Recalcular capacidades")
recalcular_ubi = col2.button("🎲 Reubicar emergencias")
calcular = col3.button("🚑 Calcular rutas")

if recalcular_cap or "G" not in st.session_state:
    st.session_state.G = asignar_capacidades(G.copy(), Cmin, Cmax)

if recalcular_ubi:
    st.session_state.base = random.choice(nodos)
    st.session_state.emergencias = {
        "E1": {"nodo": random.choice(nodos), "tipo": "leve"},
        "E2": {"nodo": random.choice(nodos), "tipo": "media"},
        "E3": {"nodo": random.choice(nodos), "tipo": "critica"},
    }

st.session_state.emergencias = generar_velocidades_requeridas(st.session_state.emergencias, Rmin, Rmax)

if calcular or "rutas" not in st.session_state:
    rutas, estado = optimizar_multiflujo(
        st.session_state.G, st.session_state.base, st.session_state.emergencias, costos
    )
    st.session_state.rutas = rutas
    st.session_state.estado = estado

# ============================================================
# INDICADOR DE ESTADO DEL MODELO
# ============================================================
st.subheader("📈 Estado del modelo")

estado = st.session_state.get("estado", "Sin calcular")

if estado == "Optimal":
    st.success("✅ Modelo resuelto correctamente: **Óptimo**")
elif estado in ["Feasible", "Optimal"]:
    st.info("ℹ️ Modelo **factible** pero no óptimo.")
elif "Infeasible" in estado:
    st.error("❌ Modelo **inviable o sin rutas posibles**.")
else:
    st.warning(f"⚠️ Estado del modelo: {estado}")

# ============================================================
# MAPA
# ============================================================
m = folium.Map(location=[6.243, -75.588], zoom_start=15, tiles="cartodbpositron")

# Base
lat_b, lon_b = G.nodes[st.session_state.base]["y"], G.nodes[st.session_state.base]["x"]
folium.Marker(
    [lat_b, lon_b],
    popup="🚑 Base de ambulancias",
    tooltip="Base",
    icon=folium.Icon(color="blue", icon="home"),
).add_to(m)

colores = {"leve": "green", "media": "orange", "critica": "red"}

for e in st.session_state.get("rutas", []):
    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in e["ruta"]]
    folium.PolyLine(
        coords,
        color=colores[e["tipo"]],
        weight=6,
        opacity=0.8,
        tooltip=f"{e['emergencia']} ({e['tipo']})\nVel Req: {round(e['vel_requerida'],1)} km/h\nCosto: {e['costo']}",
    ).add_to(m)

    lat_e, lon_e = G.nodes[e["ruta"][-1]]["y"], G.nodes[e["ruta"][-1]]["x"]
    folium.Marker(
        [lat_e, lon_e],
        popup=f"{e['emergencia']} - {e['tipo']}",
        tooltip=f"Emergencia {e['emergencia']}",
        icon=folium.Icon(color=colores[e["tipo"]], icon="info-sign"),
    ).add_to(m)

st_folium(m, width=1300, height=600)

# ============================================================
# TABLA DE RESULTADOS
# ============================================================
if st.session_state.get("rutas"):
    st.subheader("📊 Resultados de asignación de ambulancias")
    st.table(
        [
            {
                "Emergencia": e["emergencia"],
                "Tipo": e["tipo"],
                "Vel requerida (km/h)": round(e["vel_requerida"], 2),
                "Distancia (m)": round(e["distancia"], 2),
                "Costo operativo": e["costo"],
            }
            for e in st.session_state.rutas
        ]
    )
else:
    st.info("ℹ️ No hay rutas calculadas o el modelo fue infactible.")
