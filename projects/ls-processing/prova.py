import json
import os
import numpy as np
from PIL import Image, ImageDraw

# === Configura i percorsi ===
json_path = './4096_Palazzo_Maresa/project-4-at-2025-02-11-23-56-244834c1.json'     # Il file JSON esportato da Label Studio
output_dir = './masks/'              # Cartella di output per le maschere
image_dir = './4096_Palazzo_Maresa'              # Cartella contenente le immagini originali

# === Crea la cartella di output se non esiste ===
os.makedirs(output_dir, exist_ok=True)

# === Funzione per disegnare il poligono ===
def create_mask(image_size, polygons):
    mask = Image.new('L', image_size, 0)  # Maschera in scala di grigi (0 = sfondo)
    draw = ImageDraw.Draw(mask)
    for polygon in polygons:
        points = [(point[0], point[1]) for point in polygon]
        draw.polygon(points, outline=1, fill=255)  # Disegna e riempie il poligono
    return mask

# === Carica i dati JSON ===
with open(json_path, 'r') as f:
    input_data = json.load(f)

# === Itera sulle annotazioni ===
for item in input_data:
    # Recupera il nome dell'immagine
    raw_image_name = os.path.basename(item.get('data', {}).get('image', f'image_{item["id"]}'))
    print(f"raw_image_name {raw_image_name}")

    # # Rimuove il prefisso UUID (se presente) usando Python puro
    # parts = raw_image_name.split('_')
    # if len(parts) > 1:
    #     image_name = '_'.join(parts[1:]).split('.')[0]  # Prende tutto tranne il primo segmento
    # else:
    #     image_name = raw_image_name.split('.')[0]

    image_name = raw_image_name.split('-')[1]

    # Stampa di debug per verificare il nome immagine corretto
    print(f"🔍 Tentativo di apertura immagine: {image_name}")

    # Prova con diverse estensioni comuni
    possible_extensions = ['.png', '.jpg', '.jpeg']
    image_found = False

    image_path = os.path.join(image_dir, image_name)
    if os.path.exists(image_path):
        image_found = True
        

    if not image_found:
        print(f"⚠️ Immagine non trovata: {image_name}. Maschera non generata per questo file.")
        continue

    # Carica l'immagine per ottenere la dimensione corretta
    with Image.open(image_path) as img:
        image_size = img.size

    polygons = []
    for annotation in item.get('annotations', []):
        for result in annotation.get('result', []):
            if result['type'] == 'polygonlabels':  # Correzione del tipo
                points = result['value']['points']
                # Normalizza i punti rispetto alla dimensione dell'immagine
                abs_points = [(int(x * image_size[0] / 100), int(y * image_size[1] / 100)) for x, y in points]
                polygons.append(abs_points)

    # Crea la maschera
    mask = create_mask(image_size, polygons)

    # Salva la maschera come PNG
    mask.save(f'{output_dir}/{image_name}_mask.png')

print("✅ Maschere PNG generate con successo!")
