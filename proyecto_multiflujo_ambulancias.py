import streamlit as st
import networkx as nx
import osmnx as ox
import random
import folium
from pulp import LpProblem, LpVariable, lpSum, LpMinimize, LpStatus
from streamlit_folium import st_folium

# ==============================
# CONFIGURACIÓN DE LA APP
# ==============================
st.set_page_config(page_title="Optimización de Ambulancias", layout="wide")

# ==============================
# FUNCIÓN PARA CARGAR GRAFO
# ==============================
@st.cache_data(show_spinner=False)
def cargar_grafo():
    G = ox.graph_from_point((6.2406, -75.5896), dist=560, network_type='drive')
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G

G = cargar_grafo()

# ==============================
# FUNCIONES AUXILIARES
# ==============================
def generar_puntos(G, n_emergencias=5):
    nodos = list(G.nodes)
    base = random.choice(nodos)
    emergencias = random.sample(nodos, n_emergencias)
    return base, emergencias

if "base" not in st.session_state:
    st.session_state.base, st.session_state.emergencias = generar_puntos(G)
if "estado_modelo" not in st.session_state:
    st.session_state.estado_modelo = "No resuelto"

# ==============================
# SIDEBAR
# ==============================
with st.sidebar:
    st.markdown("### ⚙️ Configuración de parámetros")

    vel_min = st.slider("Velocidad mínima requerida (km/h)", 10, 50, 30)
    vel_max = st.slider("Velocidad máxima requerida (km/h)", 40, 100, 60)
    cap_min = st.slider("Capacidad mínima de vía (km/h)", 10, 50, 20)
    cap_max = st.slider("Capacidad máxima de vía (km/h)", 60, 120, 80)

    st.markdown("### 💰 Costos operativos de ambulancias")
    costo_leve = st.number_input("Transporte simple (Leve)", 50, 300, 100)
    costo_media = st.number_input("Cuidados intermedios (Media)", 100, 400, 200)
    costo_critica = st.number_input("Cuidados críticos (Crítica)", 200, 600, 300)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 Recalcular capacidades"):
            G = cargar_grafo()
    with col2:
        if st.button("🎲 Recalcular ubicaciones"):
            st.session_state.base, st.session_state.emergencias = generar_puntos(G)
            st.session_state.estado_modelo = "Ubicaciones actualizadas"
    with col3:
        calcular = st.button("🚑 Calcular rutas óptimas")

    st.markdown("---")
    st.markdown("### 📊 Estado del modelo:")

    # Bloque persistente para estado
    estado_placeholder = st.empty()
    estado = st.session_state.estado_modelo
    if "óptimo" in estado.lower():
        color = "green"
    elif "inf" in estado.lower():
        color = "red"
    else:
        color = "orange"
    estado_placeholder.markdown(f"<span style='color:{color}; font-size:18px; font-weight:bold;'>{estado}</span>", unsafe_allow_html=True)

# ==============================
# OPTIMIZACIÓN CON PULP
# ==============================
def optimizar_rutas(G, base, emergencias, costo_leve, costo_media, costo_critica):
    model = LpProblem("Rutas_Ambulancias", LpMinimize)

    tipos = ["Leve", "Media", "Crítica"]
    costos = {"Leve": costo_leve, "Media": costo_media, "Crítica": costo_critica}
    arcos = list(G.edges)

    x = LpVariable.dicts("x", (tipos, arcos), lowBound=0, cat="Continuous")

    model += lpSum(G[u][v][0]['length'] * costos[t] * x[t][(u, v)] for t in tipos for (u, v) in arcos)

    # Cada emergencia debe ser atendida
    for e in emergencias:
        model += lpSum(x[t][(u, v)] for t in tipos for (u, v) in arcos if v == e) >= 1, f"Atencion_{e}"

    # Restricciones de capacidad
    for (u, v) in arcos:
        capacidad = random.uniform(cap_min, cap_max)
        model += lpSum(x[t][(u, v)] for t in tipos) <= capacidad, f"Cap_{u}_{v}"

    model.solve()
    return model, LpStatus[model.status]

# ==============================
# EJECUCIÓN DEL MODELO
# ==============================
if calcular:
    model, estado = optimizar_rutas(G, st.session_state.base, st.session_state.emergencias, costo_leve, costo_media, costo_critica)
    st.session_state.estado_modelo = estado

# ==============================
# MAPA
# ==============================
m = folium.Map(location=[6.2406, -75.5896], zoom_start=16)

# Base
folium.Marker(
    location=(G.nodes[st.session_state.base]['y'], G.nodes[st.session_state.base]['x']),
    popup="🚑 Base de ambulancias",
    icon=folium.Icon(color="blue", icon="home"),
).add_to(m)

# Emergencias
for i, e in enumerate(st.session_state.emergencias):
    folium.Marker(
        location=(G.nodes[e]['y'], G.nodes[e]['x']),
        popup=f"Emergencia #{i+1}",
        icon=folium.Icon(color="red", icon="medkit"),
    ).add_to(m)

# Mostrar mapa
st_folium(m, width=900, height=600)
