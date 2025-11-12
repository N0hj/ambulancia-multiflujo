# proyecto_multiflujo_ambulancias.py

import streamlit as st
import osmnx as ox
import networkx as nx
import pulp
import folium
import pandas as pd

# --------------------------------------------------
# 1️⃣ Configuración inicial de la app
# --------------------------------------------------
st.set_page_config(page_title="Modelo Multiflujo de Ambulancias", layout="wide")
st.title("🚑 Modelo de Enrutamiento Multiflujo de Ambulancias")

st.sidebar.header("Configuración de parámetros")

# Parámetros ajustables por el usuario
Rmin = st.sidebar.slider("Velocidad mínima requerida (km/h)", 10, 60, 20)
Rmax = st.sidebar.slider("Velocidad máxima requerida (km/h)", 30, 120, 80)
Cmin = st.sidebar.slider("Capacidad mínima de vía (km/h)", 10, 50, 20)
Cmax = st.sidebar.slider("Capacidad máxima de vía (km/h)", 50, 120, 80)

# Coordenadas de ejemplo (zona 1 km² en Medellín)
center_point = (6.2442, -75.5812)  # Medellín centro

# --------------------------------------------------
# 2️⃣ Descargar y procesar red vial con OSMnx
# --------------------------------------------------
st.subheader("📍 Cargando red vial desde OSM...")

try:
    with st.spinner("Descargando red de OpenStreetMap..."):
        G = ox.graph_from_point(center_point, dist=500, network_type="drive")
        G = G.to_undirected()
        st.success(f"Red cargada correctamente con {len(G.nodes)} nodos y {len(G.edges)} aristas.")

except Exception as e:
    st.error(f"Error al cargar la red: {e}")
    st.stop()

# --------------------------------------------------
# 3️⃣ Asignar velocidades aleatorias a las calles
# --------------------------------------------------
import random
for u, v, data in G.edges(data=True):
    data["capacity"] = random.uniform(Cmin, Cmax)
    data["speed"] = random.uniform(Rmin, Rmax)

# --------------------------------------------------
# 4️⃣ Definir nodos de base y emergencias simuladas
# --------------------------------------------------
st.subheader("🚨 Simulación de emergencias")

base_node = list(G.nodes())[0]
dest_nodes = random.sample(list(G.nodes()), 3)
tipos = ["crítica", "media", "leve"]
incidentes = {dest_nodes[i]: tipos[i] for i in range(3)}

st.write("📋 Nodos de emergencia generados:")
st.json(incidentes)

# --------------------------------------------------
# 5️⃣ Modelo de optimización (simplificado)
# --------------------------------------------------
st.subheader("🧮 Cálculo de rutas óptimas")

try:
    # Variables y modelo básico (dummy, ejemplo)
    model = pulp.LpProblem("RutasAmbulancias", pulp.LpMinimize)

    # En esta versión no se calcula el flujo real aún, solo se define estructura
    # Luego podrás incluir aquí tus variables x[i,j,k] y restricciones

    st.info("Modelo preparado (versión simplificada).")

    # Generamos una lista vacía para mostrar estructura del mapa
    edges_selected = []

except Exception as e:
    st.error(f"Error en el modelo: {e}")
    edges_selected = []

# --------------------------------------------------
# 6️⃣ Visualización del mapa
# --------------------------------------------------
st.subheader("🗺️ Visualización de la red y rutas")

try:
    # Crear mapa base
    m = ox.plot_graph_folium(G, color="gray", weight=1)

    # Marcadores
    folium.Marker(location=center_point, popup="Base de Ambulancias 🏥",
                  icon=folium.Icon(color="blue")).add_to(m)

    for node, tipo in incidentes.items():
        folium.Marker(location=(G.nodes[node]["y"], G.nodes[node]["x"]),
                      popup=f"Emergencia {tipo}",
                      icon=folium.Icon(color="red" if tipo == "crítica" else "orange" if tipo == "media" else "green")
                      ).add_to(m)

    # Dibujar rutas (solo si existen)
    if edges_selected:
        for (u, v) in edges_selected:
            folium.PolyLine([(G.nodes[u]['y'], G.nodes[u]['x']),
                             (G.nodes[v]['y'], G.nodes[v]['x'])],
                            color="red", weight=4).add_to(m)
    else:
        st.warning("Aún no se han calculado rutas óptimas (modelo simplificado).")

    st.components.v1.html(m._repr_html_(), height=600)

except Exception as e:
    st.error(f"Error al mostrar el mapa: {e}")
