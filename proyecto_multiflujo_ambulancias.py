# ============================================================
# 🚑 PROYECTO: Optimización de rutas de ambulancias (Multiflujo)
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

st.title("🚑 Optimización de rutas de ambulancias - Modelo multiflujo con PuLP")
st.sidebar.header("⚙️ Configuración de parámetros")

# ============================================================
# PARÁMETROS CONFIGURABLES (por defecto balanceados)
# ============================================================
Rmin = st.sidebar.slider("Velocidad mínima requerida (km/h)", 10, 100, 20)
Rmax = st.sidebar.slider("Velocidad máxima requerida (km/h)", 20, 120, 50)
Cmin = st.sidebar.slider("Capacidad mínima de vía (km/h)", 10, 100, 40)
Cmax = st.sidebar.slider("Capacidad máxima de vía (km/h)", 20, 120, 80)

st.sidebar.markdown("---")
st.sidebar.subheader("💰 Costos operativos de ambulancias")

costos = {
    "leve": st.sidebar.number_input("Transporte simple (Leve)", min_value=50, max_value=500, value=100),
    "media": st.sidebar.number_input("Cuidados intermedios (Media)", min_value=100, max_value=600, value=200),
    "critica": st.sidebar.number_input("Cuidados críticos (Crítica)", min_value=150, max_value=800, value=300),
}

# ============================================================
# DESCARGA Y PROCESO DE MAPA
# ============================================================
@st.cache_data
def cargar_mapa():
    lat, lon = 6.2433, -75.5881  # San Joaquín, Medellín
    G = ox.graph_from_point((lat, lon), dist=800, network_type="drive")
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G

G = cargar_mapa()

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================
def asignar_capacidades(G, cmin, cmax):
    """Asigna una capacidad (velocidad máxima) aleatoria a cada vía."""
    for u, v, k, data in G.edges(keys=True, data=True):
        data["capacidad"] = random.uniform(cmin, cmax)
    return G

def generar_velocidades_requeridas(emergencias, rmin, rmax):
    """Genera velocidades requeridas (Ri) aleatorias para cada flujo."""
    for e in emergencias.values():
        e["vel_requerida"] = random.uniform(rmin, rmax)
    return emergencias

# ============================================================
# CREACIÓN DE BASE Y EMERGENCIAS
# ============================================================
nodos = list(G.nodes())
if "base" not in st.session_state:
    st.session_state.base = random.choice(nodos)

if "emergencias" not in st.session_state:
    st.session_state.emergencias = {
        "E1": {"nodo": random.choice(nodos), "tipo": "leve"},
        "E2": {"nodo": random.choice(nodos), "tipo": "media"},
        "E3": {"nodo": random.choice(nodos), "tipo": "critica"},
    }

# ============================================================
# MODELO DE OPTIMIZACIÓN MULTIFLUJO CON PuLP
# ============================================================
def optimizar_con_pulp(G, base, emergencias, costos):
    prob = pulp.LpProblem("Ruteo_de_Ambulancias", pulp.LpMinimize)

    # Variables binarias x_(u,v,k)
    x = pulp.LpVariable.dicts("x", ((u, v, k) for u, v, k in G.edges(keys=True)), cat="Binary")

    # Función objetivo
    prob += pulp.lpSum(
        G[u][v][k]["length"] * costos[e["tipo"]] * x[(u, v, k)]
        for u, v, k in G.edges(keys=True)
        for e in emergencias.values()
    )

    # Restricciones de capacidad
    for u, v, k, data in G.edges(keys=True, data=True):
        prob += pulp.lpSum(x[(u, v, k)]) <= 1

    # Restricciones de flujo
    for nombre, e in emergencias.items():
        nodo_origen = base
        nodo_destino = e["nodo"]

        for n in G.nodes():
            in_edges = [(u, v, k) for u, v, k in G.in_edges(n, keys=True)]
            out_edges = [(u, v, k) for u, v, k in G.out_edges(n, keys=True)]

            if n == nodo_origen:
                prob += pulp.lpSum(x[(u, v, k)] for u, v, k in out_edges) - pulp.lpSum(
                    x[(u, v, k)] for u, v, k in in_edges
                ) == 1
            elif n == nodo_destino:
                prob += pulp.lpSum(x[(u, v, k)] for u, v, k in in_edges) - pulp.lpSum(
                    x[(u, v, k)] for u, v, k in out_edges
                ) == 1
            else:
                prob += pulp.lpSum(x[(u, v, k)] for u, v, k in out_edges) - pulp.lpSum(
                    x[(u, v, k)] for u, v, k in in_edges
                ) == 0

    # Resolver modelo
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    estado = pulp.LpStatus[status]

    # Extraer rutas si es factible
    rutas = []
    if estado in ["Optimal", "Feasible"]:
        for nombre, e in emergencias.items():
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
# BOTONES DE INTERACCIÓN
# ============================================================
col1, col2, col3 = st.sidebar.columns(3)
recalcular_cap = col1.button("🔄 Recalcular capacidades")
recalcular_ubi = col2.button("🎲 Recalcular ubicaciones")
calcular = col3.button("🚑 Calcular rutas óptimas")

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
    st.session_state.rutas, st.session_state.estado = optimizar_con_pulp(
        st.session_state.G, st.session_state.base, st.session_state.emergencias, costos
    )

# ============================================================
# INDICADOR DE ESTADO DEL MODELO
# ============================================================
if "estado" in st.session_state:
    if st.session_state.estado in ["Optimal", "Feasible"]:
        st.success(f"✅ Optimización completada ({st.session_state.estado})")
    else:
        st.error(f"⚠️ Optimización no factible ({st.session_state.estado})")

# ============================================================
# MAPA INTERACTIVO
# ============================================================
m = folium.Map(location=[6.243, -75.588], zoom_start=15, tiles="cartodbpositron")

lat_b, lon_b = G.nodes[st.session_state.base]["y"], G.nodes[st.session_state.base]["x"]
folium.Marker([lat_b, lon_b], popup="🚑 Base de ambulancias", icon=folium.Icon(color="blue", icon="home")).add_to(m)

colores = {"leve": "green", "media": "orange", "critica": "red"}

for e in st.session_state.rutas:
    tipo = e["tipo"]
    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in e["ruta"]]
    folium.PolyLine(coords, color=colores[tipo], weight=6, opacity=0.8,
                    tooltip=f"{e['emergencia']} ({tipo})\nVel Req: {round(e['vel_requerida'],1)} km/h\nCosto: {e['costo']}").add_to(m)
    lat_e, lon_e = G.nodes[e["ruta"][-1]]["y"], G.nodes[e["ruta"][-1]]["x"]
    folium.Marker([lat_e, lon_e], popup=f"{e['emergencia']} - {tipo}", icon=folium.Icon(color=colores[tipo])).add_to(m)

st_folium(m, width=1300, height=600)

# ============================================================
# TABLA DE RESULTADOS
# ============================================================
if st.session_state.estado in ["Optimal", "Feasible"]:
    st.subheader("📊 Resultados de asignación de ambulancias")
    st.table(
        [
            {
                "Emergencia": e["emergencia"],
                "Tipo": e["tipo"],
                "Vel. requerida (km/h)": round(e["vel_requerida"], 2),
                "Distancia (m)": round(e["distancia"], 2),
                "Costo operativo": e["costo"],
            }
            for e in st.session_state.rutas
        ]
    )
