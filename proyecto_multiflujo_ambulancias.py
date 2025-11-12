import streamlit as st
import osmnx as ox
import networkx as nx
import random
import folium

# --------------------------------------------------
# Configuración general
# --------------------------------------------------
st.set_page_config(page_title="Modelo Multiflujo de Ambulancias", layout="wide")
st.title("🚑 Modelo de Enrutamiento Multiflujo de Ambulancias")

st.sidebar.header("⚙️ Configuración de parámetros")

# Parámetros configurables
Rmin = st.sidebar.slider("Velocidad mínima requerida (km/h)", 10, 60, 20)
Rmax = st.sidebar.slider("Velocidad máxima requerida (km/h)", 30, 120, 80)
Cmin = st.sidebar.slider("Capacidad mínima de vía (km/h)", 10, 50, 20)
Cmax = st.sidebar.slider("Capacidad máxima de vía (km/h)", 50, 120, 80)

# --------------------------------------------------
# Cargar red vial
# --------------------------------------------------
center_point = (6.2442, -75.5812)
st.subheader("📍 Red vial de Medellín (zona 1 km²)")

with st.spinner("Cargando red de OpenStreetMap..."):
    G = ox.graph_from_point(center_point, dist=500, network_type="drive")
    G = G.to_undirected()

# --------------------------------------------------
# Función: asignar capacidades
# --------------------------------------------------
def asignar_capacidades(G, Cmin, Cmax, Rmin, Rmax):
    for u, v, data in G.edges(data=True):
        data["capacity"] = random.uniform(Cmin, Cmax)
        data["speed"] = random.uniform(Rmin, Rmax)
        # Peso inverso a la velocidad: rutas más rápidas = menor costo
        data["weight"] = 1 / data["speed"]
    return G

# Botón para recalcular capacidades
if st.button("🔁 Recalcular capacidades de las vías"):
    G = asignar_capacidades(G, Cmin, Cmax, Rmin, Rmax)
    st.success("Capacidades y velocidades recalculadas.")

# Si no se ha presionado el botón antes
if "capacidades_asignadas" not in st.session_state:
    G = asignar_capacidades(G, Cmin, Cmax, Rmin, Rmax)
    st.session_state.capacidades_asignadas = True

# --------------------------------------------------
# Nodos base y emergencias
# --------------------------------------------------
st.subheader("🚨 Emergencias simuladas")
base_node = list(G.nodes())[0]
dest_nodes = random.sample(list(G.nodes()), 3)
tipos = ["crítica", "media", "leve"]
requerimientos = {"crítica": Rmax * 0.9, "media": Rmax * 0.7, "leve": Rmax * 0.5}
incidentes = {dest_nodes[i]: tipos[i] for i in range(3)}
st.json(incidentes)

# --------------------------------------------------
# Cálculo de rutas (botón)
# --------------------------------------------------
st.subheader("🧮 Cálculo de rutas óptimas")

edges_selected = []
rutas = {}

if st.button("🚦 Recalcular flujos"):
    st.info("Ejecutando modelo de rutas...")

    for destino, tipo in incidentes.items():
        try:
            ruta = nx.shortest_path(G, source=base_node, target=destino, weight="weight")
            rutas[tipo] = ruta
            # Guardar aristas para el mapa
            for i in range(len(ruta) - 1):
                edges_selected.append((ruta[i], ruta[i + 1]))
        except Exception as e:
            st.error(f"No se pudo calcular ruta para {tipo}: {e}")

    st.success("✅ Rutas recalculadas correctamente.")

# --------------------------------------------------
# Mapa
# --------------------------------------------------
st.subheader("🗺️ Visualización de rutas")

m = ox.plot_graph_folium(G, color="gray", weight=1)

# Base
folium.Marker(
    location=(G.nodes[base_node]["y"], G.nodes[base_node]["x"]),
    popup="Base de ambulancias 🏥",
    icon=folium.Icon(color="blue"),
).add_to(m)

# Destinos
for node, tipo in incidentes.items():
    folium.Marker(
        location=(G.nodes[node]["y"], G.nodes[node]["x"]),
        popup=f"Emergencia {tipo}",
        icon=folium.Icon(color="red" if tipo == "crítica" else "orange" if tipo == "media" else "green"),
    ).add_to(m)

# Dibujar rutas si existen
colores = {"crítica": "red", "media": "orange", "leve": "green"}
for tipo, ruta in rutas.items():
    puntos = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in ruta]
    folium.PolyLine(puntos, color=colores[tipo], weight=5, tooltip=f"Ruta {tipo}").add_to(m)

st.components.v1.html(m._repr_html_(), height=600)
