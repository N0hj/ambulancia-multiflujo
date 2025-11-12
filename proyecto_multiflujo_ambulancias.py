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
st.set_page_config(
    page_title="Optimización de rutas de ambulancias",
    layout="wide",
)

st.title("🚑 Optimización de rutas de ambulancias - Modelo multiflujo (1 base, múltiples emergencias)")

st.sidebar.header("⚙️ Configuración de parámetros")

# =========================
# PARÁMETROS CONFIGURABLES
# =========================
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

# =========================
# DESCARGA Y PROCESO DE MAPA
# =========================
@st.cache_data
def cargar_mapa():
    lat, lon = 6.2433, -75.5881  # San Joaquín, Medellín
    G = ox.graph_from_point((lat, lon), dist=800, network_type='drive')
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G

G = cargar_mapa()

# =========================
# FUNCIONES AUXILIARES
# =========================
def asignar_capacidades(G, cmin, cmax):
    for u, v, k, data in G.edges(keys=True, data=True):
        data["capacidad"] = random.uniform(cmin, cmax)
    return G

# =========================
# GENERACIÓN DE BASE Y EMERGENCIAS
# =========================
nodos = list(G.nodes())

if "base" not in st.session_state:
    st.session_state.base = random.choice(nodos)

if "emergencias" not in st.session_state:
    st.session_state.emergencias = {
        "E1": {"nodo": random.choice(nodos), "tipo": "leve"},
        "E2": {"nodo": random.choice(nodos), "tipo": "media"},
        "E3": {"nodo": random.choice(nodos), "tipo": "critica"},
    }

base = st.session_state.base
emergencias = st.session_state.emergencias

# =========================
# FUNCIÓN DE OPTIMIZACIÓN
# =========================
def optimizar_asignacion(G, base, emergencias, costos):
    rutas = []
    for e, info in emergencias.items():
        tipo = info["tipo"]
        costo = costos[tipo]
        nodo_emergencia = info["nodo"]

        try:
            dist = nx.shortest_path_length(G, base, nodo_emergencia, weight='length')
            path = nx.shortest_path(G, base, nodo_emergencia, weight='length')

            rutas.append({
                "emergencia": e,
                "tipo": tipo,
                "ruta": path,
                "distancia": dist,
                "costo": costo
            })
        except nx.NetworkXNoPath:
            st.warning(f"No hay ruta disponible entre la base y {e}.")
    return rutas

# =========================
# BOTONES DE INTERACCIÓN
# =========================
col1, col2 = st.sidebar.columns(2)
recalcular_cap = col1.button("🔄 Recalcular capacidades")
recalcular_flujos = col2.button("🚨 Recalcular flujos")

if "G" not in st.session_state or recalcular_cap:
    st.session_state.G = asignar_capacidades(G.copy(), Cmin, Cmax)

if recalcular_flujos or "rutas" not in st.session_state:
    st.session_state.rutas = optimizar_asignacion(st.session_state.G, base, emergencias, costos)

# =========================
# MAPA INTERACTIVO
# =========================
m = folium.Map(location=[6.243, -75.584], zoom_start=15, tiles="cartodbpositron")
colores = {"leve": "green", "media": "orange", "critica": "red"}

# Marcar base
lat_b, lon_b = G.nodes[base]['y'], G.nodes[base]['x']
folium.Marker(
    [lat_b, lon_b],
    popup="🚑 Base de ambulancias",
    tooltip="Base principal",
    icon=folium.Icon(color="blue", icon="hospital", prefix="fa")
).add_to(m)

# Dibujar rutas y emergencias
for e in st.session_state.rutas:
    tipo = e["tipo"]
    path = e["ruta"]
    coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path]
    color = colores[tipo]

    folium.PolyLine(coords, color=color, weight=6, opacity=0.8,
                    tooltip=f"{e['emergencia']} ({tipo})").add_to(m)

    lat_e, lon_e = G.nodes[path[-1]]['y'], G.nodes[path[-1]]['x']
    folium.Marker(
        [lat_e, lon_e],
        icon=folium.Icon(color=color, icon="exclamation-triangle", prefix="fa"),
        popup=f"{e['emergencia']} - Urgencia: {tipo}\nCosto: {e['costo']}"
    ).add_to(m)

st_folium(m, width=1300, height=600)

# =========================
# TABLA DE RESULTADOS
# =========================
st.subheader("📊 Resultados de asignación")
st.write("Cada flujo corresponde a una emergencia atendida desde la única base de ambulancias.")

st.table([
    {
        "Emergencia": e["emergencia"],
        "Tipo": e["tipo"],
        "Distancia (m)": round(e["distancia"], 2),
        "Costo operativo": e["costo"]
    }
    for e in st.session_state.rutas
])
