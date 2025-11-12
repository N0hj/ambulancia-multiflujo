# ============================================================
# 🚑 PROYECTO: Optimización de rutas de ambulancias (Multiflujo)
# Autor: [Tu Nombre]
# Universidad Pontificia Bolivariana (UPB)
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
st.set_page_config(
    page_title="Optimización de rutas de ambulancias",
    layout="wide",
)

st.title("🚑 Optimización de rutas de ambulancias - Modelo multiflujo con PuLP")
st.sidebar.header("⚙️ Configuración de parámetros")

# ============================================================
# PARÁMETROS CONFIGURABLES
# ============================================================
Rmin = st.sidebar.slider("Velocidad mínima requerida (km/h)", 10, 100, 30)
Rmax = st.sidebar.slider("Velocidad máxima requerida (km/h)", 20, 120, 60)
Cmin = st.sidebar.slider("Capacidad mínima de vía (km/h)", 10, 100, 20)
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
    # Zona de estudio ≈1 km² centrada en San Joaquín, Medellín
    lat, lon = 6.2433, -75.5881
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

def nodos_conectados(G, base, cantidad=3):
    """Selecciona nodos conectados al nodo base (misma componente)."""
    # Convertir a componente fuertemente o débilmente conectada según tipo de grafo
    componentes = list(nx.strongly_connected_components(G.to_directed()))
    for c in componentes:
        if base in c:
            componente = c
            break
    # Si hay menos de 'cantidad' nodos, usa los disponibles
    disponibles = list(componente - {base})
    if len(disponibles) < cantidad:
        cantidad = len(disponibles)
    return random.sample(disponibles, cantidad)

# ============================================================
# CREACIÓN DE BASE Y EMERGENCIAS
# ============================================================
nodos = list(G.nodes())

if "base" not in st.session_state:
    st.session_state.base = random.choice(nodos)

if "emergencias" not in st.session_state:
    nodos_validos = nodos_conectados(G, st.session_state.base)
    st.session_state.emergencias = {
        "E1": {"nodo": nodos_validos[0], "tipo": "leve"},
        "E2": {"nodo": nodos_validos[1], "tipo": "media"},
        "E3": {"nodo": nodos_validos[2], "tipo": "critica"},
    }

# ============================================================
# MODELO DE OPTIMIZACIÓN MULTIFLUJO CON PuLP
# ============================================================
def optimizar_con_pulp(G, base, emergencias, costos):
    """
    Modelo multiflujo (multi-commodity flow) que minimiza el costo total
    de atención de emergencias considerando capacidad de vías y costos operativos.
    """

    # Crear problema de optimización
    prob = pulp.LpProblem("Ruteo_de_Ambulancias", pulp.LpMinimize)

    # Variables binarias x_(u,v,e): si emergencia e usa el arco (u,v)
    x = pulp.LpVariable.dicts(
        "x",
        ((u, v, k, e) for u, v, k in G.edges(keys=True) for e in emergencias),
        cat="Binary"
    )

    # Función objetivo: minimizar costo total (distancia * costo operativo)
    prob += pulp.lpSum(
        G[u][v][k]["length"] * costos[emergencias[e]["tipo"]] * x[(u, v, k, e)]
        for u, v, k in G.edges(keys=True)
        for e in emergencias
    )

    # Restricciones de capacidad: solo una ambulancia puede usar una vía a la vez
    for u, v, k, data in G.edges(keys=True, data=True):
        prob += pulp.lpSum(x[(u, v, k, e)] for e in emergencias) <= 1

    # Conservación de flujo
    for e, info in emergencias.items():
        nodo_origen = base
        nodo_destino = info["nodo"]

        for n in G.nodes():
            in_edges = [(u, v, k) for u, v, k in G.in_edges(n, keys=True)]
            out_edges = [(u, v, k) for u, v, k in G.out_edges(n, keys=True)]

            if n == nodo_origen:
                prob += pulp.lpSum(x[(u, v, k, e)] for u, v, k in out_edges) - pulp.lpSum(
                    x[(u, v, k, e)] for u, v, k in in_edges
                ) == 1
            elif n == nodo_destino:
                prob += pulp.lpSum(x[(u, v, k, e)] for u, v, k in in_edges) - pulp.lpSum(
                    x[(u, v, k, e)] for u, v, k in out_edges
                ) == 1
            else:
                prob += pulp.lpSum(x[(u, v, k, e)] for u, v, k in out_edges) - pulp.lpSum(
                    x[(u, v, k, e)] for u, v, k in in_edges
                ) == 0

    # Resolver modelo
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # Extraer rutas más cortas reales (usando NetworkX)
    rutas = []
    for e, info in emergencias.items():
        tipo = info["tipo"]
        try:
            path = nx.shortest_path(G, base, info["nodo"], weight="length")
            distancia = nx.shortest_path_length(G, base, info["nodo"], weight="length")
        except nx.NetworkXNoPath:
            continue

        rutas.append(
            {
                "emergencia": e,
                "tipo": tipo,
                "vel_requerida": info["vel_requerida"],
                "ruta": path,
                "distancia": distancia,
                "costo": costos[tipo],
            }
        )

    if pulp.LpStatus[prob.status] != "Optimal":
        st.warning(f"⚠️ Optimización completada con estado: {pulp.LpStatus[prob.status]}")

    return rutas

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
    nodos_validos = nodos_conectados(G, st.session_state.base)
    st.session_state.emergencias = {
        "E1": {"nodo": nodos_validos[0], "tipo": "leve"},
        "E2": {"nodo": nodos_validos[1], "tipo": "media"},
        "E3": {"nodo": nodos_validos[2], "tipo": "critica"},
    }

# Generar velocidades requeridas
st.session_state.emergencias = generar_velocidades_requeridas(
    st.session_state.emergencias, Rmin, Rmax
)

if calcular or "rutas" not in st.session_state:
    st.session_state.rutas = optimizar_con_pulp(
        st.session_state.G, st.session_state.base, st.session_state.emergencias, costos
    )

# ============================================================
# MAPA INTERACTIVO
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

# Colores
colores = {"leve": "green", "media": "orange", "critica": "red"}

# Rutas y emergencias
for e in st.session_state.rutas:
    tipo = e["tipo"]
    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in e["ruta"]]
    folium.PolyLine(
        coords,
        color=colores[tipo],
        weight=6,
        opacity=0.8,
        tooltip=f"{e['emergencia']} ({tipo}) | Vel Req: {round(e['vel_requerida'], 1)} km/h | Costo: {e['costo']}",
    ).add_to(m)

    lat_e, lon_e = G.nodes[e["ruta"][-1]]["y"], G.nodes[e["ruta"][-1]]["x"]
    folium.Marker(
        [lat_e, lon_e],
        popup=f"{e['emergencia']} - {tipo}",
        tooltip=f"Emergencia {e['emergencia']}",
        icon=folium.Icon(color=colores[tipo], icon="info-sign"),
    ).add_to(m)

st_folium(m, width=1300, height=600)

# ============================================================
# TABLA DE RESULTADOS
# ============================================================
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
