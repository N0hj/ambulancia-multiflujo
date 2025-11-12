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

st.title("🚑 Optimización de rutas de ambulancias - Modelo multiflujo")

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
    # Descargar red vial centrada en San Joaquín, Medellín (zona segura)
    lat, lon = 6.2433, -75.5881
    G = ox.graph_from_point((lat, lon), dist=800, network_type='drive')
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    return G

G = cargar_mapa()

# =========================
# GENERACIÓN DE DATOS ALEATORIOS
# =========================
def asignar_capacidades(G, cmin, cmax):
    for u, v, k, data in G.edges(keys=True, data=True):
        data["capacidad"] = random.uniform(cmin, cmax)
    return G

def generar_requerimientos(num):
    return [random.uniform(Rmin, Rmax) for _ in range(num)]

# =========================
# PUNTOS DE EMERGENCIA Y BASES
# =========================
bases = {
    "Base 1": list(G.nodes())[100],
    "Base 2": list(G.nodes())[400],
    "Base 3": list(G.nodes())[700]
}

emergencias = {
    "E1": {"nodo": list(G.nodes())[200], "tipo": "leve"},
    "E2": {"nodo": list(G.nodes())[500], "tipo": "media"},
    "E3": {"nodo": list(G.nodes())[800], "tipo": "critica"}
}

# =========================
# ASIGNAR AMBULANCIAS Y RUTAS
# =========================
def optimizar_asignacion(G, bases, emergencias, costos):
    rutas = []
    for e, info in emergencias.items():
        tipo = info["tipo"]
        costo = costos[tipo]
        nodo_emergencia = info["nodo"]

        # Buscar base más cercana
        dist_min = float("inf")
        base_asignada = None
        for b, nodo_base in bases.items():
            try:
                dist = nx.shortest_path_length(G, nodo_base, nodo_emergencia, weight='length')
                if dist < dist_min:
                    dist_min = dist
                    base_asignada = b
            except:
                continue

        # Ruta más corta
        path = nx.shortest_path(G, bases[base_asignada], nodo_emergencia, weight='length')
        rutas.append({
            "emergencia": e,
            "tipo": tipo,
            "ambulancia": base_asignada,
            "ruta": path,
            "distancia": dist_min,
            "costo": costo
        })
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
    st.session_state.rutas = optimizar_asignacion(st.session_state.G, bases, emergencias, costos)

# =========================
# MAPA INTERACTIVO
# =========================
m = folium.Map(location=[6.243, -75.584], zoom_start=15, tiles="cartodbpositron")

# Marcar bases
for b, nodo in bases.items():
    lat, lon = G.nodes[nodo]['y'], G.nodes[nodo]['x']
    folium.Marker(
        [lat, lon], popup=f"{b}", tooltip=b,
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

# Marcar emergencias
colores = {"leve": "green", "media": "orange", "critica": "red"}

for e in st.session_state.rutas:
    tipo = e["tipo"]
    path = e["ruta"]
    coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path]
    folium.PolyLine(coords, color=colores[tipo], weight=6, opacity=0.8,
                    tooltip=f"{e['emergencia']} ({tipo}) - {e['ambulancia']}").add_to(m)
    lat_e, lon_e = G.nodes[path[-1]]['y'], G.nodes[path[-1]]['x']
    folium.Marker([lat_e, lon_e],
                  icon=folium.Icon(color=colores[tipo], icon="info-sign"),
                  popup=f"{e['emergencia']} - Urgencia: {tipo}\nCosto: {e['costo']}").add_to(m)

st_folium(m, width=1300, height=600)

# =========================
# TABLA DE RESULTADOS
# =========================
st.subheader("📊 Resultados de asignación")
st.write("Cada flujo corresponde a una emergencia atendida por una ambulancia asignada.")

st.table([
    {
        "Emergencia": e["emergencia"],
        "Tipo": e["tipo"],
        "Ambulancia asignada": e["ambulancia"],
        "Distancia (m)": round(e["distancia"], 2),
        "Costo operativo": e["costo"]
    }
    for e in st.session_state.rutas
])
