import json
import re
from datetime import datetime
import os

# Importamos la app y la base de datos para poder operar dentro del contexto de la aplicación
from backend.app import app
from backend.models import db, Event

# --- HELPERS PARA LIMPIEZA Y TRANSFORMACIÓN DE DATOS ---

def clean_text(text):
    """Elimina las referencias numéricas como [10], [14], etc."""
    if not isinstance(text, str):
        return text
    return re.sub(r'\s*\[\d+\]', '', text).strip()

def parse_spanish_date(date_str):
    """Convierte una fecha en español (ej: "9 de febrero de 2025") a un objeto date."""
    date_str = clean_text(date_str)
    
    # Tomamos la primera fecha si hay un rango como "22 y 23 de..."
    date_str = re.split(r'\s*y\s*|\s*al\s*', date_str)[0].strip()

    month_map = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    
    parts = date_str.replace('de ', '').split()
    if len(parts) != 3:
        print(f"  [AVISO] Formato de fecha no reconocido: '{date_str}'. Omitiendo.")
        return None
        
    day, month_name, year = parts
    month = month_map.get(month_name.lower())
    
    if not month:
        print(f"  [AVISO] Mes no reconocido en fecha: '{date_str}'. Omitiendo.")
        return None
        
    try:
        return datetime(int(year), month, int(day)).date()
    except ValueError as e:
        print(f"  [ERROR] No se pudo convertir la fecha '{date_str}': {e}")
        return None

def parse_location(location_str):
    """Divide la localización en ciudad y provincia."""
    location_str = clean_text(location_str)
    if ',' in location_str:
        parts = location_str.split(',', 1)
        city = parts[0].strip()
        province = parts[1].strip()
        return city, province
    else:
        # Si no hay coma, asumimos que la ciudad y la provincia son la misma
        return location_str, location_str

def normalize_discipline_distance(event_data):
    """Extrae y normaliza la disciplina y la distancia."""
    discipline_name = clean_text(event_data.get('disciplina_nombre', ''))
    distance_str = clean_text(event_data.get('distancia', ''))
    
    discipline = "No especificada"
    distance = distance_str if distance_str != "No especificada en la fuente" else "No especificada"

    if "duatlón" in discipline_name.lower():
        discipline = "Duatlón"
    elif "triatlón" in discipline_name.lower():
        discipline = "Triatlón"
    elif "acuatlón" in discipline_name.lower():
        discipline = "Acuatlón"
    elif "gravel" in discipline_name.lower():
        discipline = "Gravel"
    elif "cros" in discipline_name.lower():
        discipline = "Cros"

    if "larga distancia" in discipline_name.lower() or "ironman" in discipline_name.lower() and "70.3" not in discipline_name:
        distance = "Larga Distancia"
    if "media distancia" in discipline_name.lower() or "70.3" in discipline_name.lower() or "half" in discipline_name.lower():
        distance = "Media Distancia (70.3)"
    if "olímpico" in discipline_name.lower():
        distance = "Olímpica"
    if "sprint" in discipline_name.lower() and "super" not in discipline_name.lower():
        distance = "Sprint"
    if "supersprint" in discipline_name.lower():
        distance = "SuperSprint"

    return discipline, distance

# --- FUNCIÓN PRINCIPAL DEL SCRIPT ---

def seed_database():
    """Lee el fichero JSON y puebla la tabla de Events."""
    
    # Usamos el contexto de la aplicación para poder acceder a la BD
    with app.app_context():
        # Borrar datos existentes para evitar duplicados en ejecuciones repetidas
        db.session.query(Event).delete()
        db.session.commit()
        print("Datos antiguos de la tabla 'events' eliminados.")

        # Cargar los datos del fichero JSON
        try:
            with open('seed_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            print("Error: No se encontró el fichero 'seed_data.json'. Asegúrate de que está en la raíz del proyecto.")
            return
        
        all_events = []
        for key, value in data["calendario_triatlon_espana_2025"].items():
            if isinstance(value, list):
                all_events.extend(value)

        print(f"Se han encontrado {len(all_events)} eventos en total en el fichero JSON. Procesando...")
        
        events_added = 0
        for event_data in all_events:
            name = clean_text(event_data.get("disciplina_nombre", "Evento sin nombre"))
            print(f"Procesando: {name}...")

            event_date = parse_spanish_date(event_data.get("fecha", ""))
            if not event_date:
                continue

            # Evitar duplicados simples
            exists = db.session.query(Event).filter_by(name=name, event_date=event_date).first()
            if exists:
                print(f"  [AVISO] Evento duplicado encontrado. Omitiendo.")
                continue

            city, province = parse_location(event_data.get("localizacion", "Sede por designar"))
            discipline, distance = normalize_discipline_distance(event_data)

            new_event = Event(
                name=name,
                event_date=event_date,
                city=city,
                province=province,
                discipline=discipline,
                distance=distance,
                source_url=clean_text(event_data.get("enlace_inscripcion_detalles", ""))
                # Los campos de curación (is_good_for_debutants, etc.) se quedan en False por defecto
            )
            
            db.session.add(new_event)
            events_added += 1

        # Guardar todos los nuevos eventos en la base de datos
        db.session.commit()
        print(f"\n¡Carga inicial completada! Se han añadido {events_added} nuevos eventos a la base de datos.")


# --- EJECUCIÓN DEL SCRIPT ---
if __name__ == '__main__':
    seed_database()
