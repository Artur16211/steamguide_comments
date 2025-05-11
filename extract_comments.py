import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict
import bs4
import requests
import json
import dateparser
from pathlib import Path

# Configuración
urls = [
    'https://steamcommunity.com/sharedfiles/filedetails/?id=3476068089',
    'https://steamcommunity.com/sharedfiles/filedetails/?id=3438530146',
    'https://steamcommunity.com/sharedfiles/filedetails/?id=3478574794',
    'https://steamcommunity.com/sharedfiles/filedetails/?id=3478642806'
]

@dataclass
class Comment:
    autor: str
    message: str
    timeStamp: datetime

    def __str__(self):
        return f'[{self.timeStamp.isoformat()}] {self.autor:30}: {self.message}'

def extractFromScriptTag(scriptTag: bs4.Tag) -> Optional[str]:
    js = scriptTag.string.__str__()
    if not (ownerMatch := next(re.finditer(r'"owner": ?"(\d+)"', js), None)):
        return
    if not (feature := next(re.finditer(r'\"feature\": ?\"(\d+)"', js), None)):
        return
    return f'https://steamcommunity.com/comment/PublishedFile_Public/render/{ownerMatch.group(1)}/{feature.group(1)}/'

def extractComments(htmlText: str) -> List[Dict]:
    result = []
    bs = bs4.BeautifulSoup(htmlText, "html.parser")
    for singleComment in bs.find_all(class_='commentthread_comment responsive_body_text'):
        try:
            # Extraer avatar
            avatar_tag = singleComment.find(class_='commentthread_comment_avatar')
            avatar_url = avatar_tag.find('img')['src'] if avatar_tag and avatar_tag.find('img') else None
            
            # Obtener avatar de más alta resolución
            if avatar_url and 'steamstatic.com' in avatar_url and '_medium' not in avatar_url:
                if avatar_url.endswith('.jpg'):
                    avatar_url = avatar_url.replace('.jpg', '_medium.jpg')

            autor: str = singleComment.find('bdi').text.strip()
            message: str = singleComment.find(
                class_='commentthread_comment_text').text.strip()
            timestamp: str = singleComment.find(
                class_='commentthread_comment_timestamp')['title'].strip()

            # Limpieza de la cadena de fecha
            timestamp = timestamp.replace(',', '')  # Elimina comas
            timestamp = re.sub(r'\s+', ' ', timestamp)  # Normaliza espacios
            
            # Intenta parsear con varios formatos
            try:
                date = datetime.strptime(timestamp, '%d %B %Y @ %I:%M:%S %p')
            except ValueError:
                # Intenta con dateparser como fallback
                date = dateparser.parse(timestamp)
                if not date:
                    date = datetime.now()  # Fallback final
                    print(f"Warning: Could not parse date: {timestamp}")

            # Crear diccionario con todos los datos incluyendo el avatar
            comment_data = {
                'author': autor,
                'message': message,
                'timestamp': date.isoformat(),
                'avatar': avatar_url
            }
            result.append(comment_data)
        except Exception as e:
            print(f"Error processing comment: {str(e)}")
            continue
            
    return result

def load_existing_comments(filename: str) -> List[Dict]:
    """Carga los comentarios existentes de un archivo JSON en la carpeta docs/"""
    filepath = Path('docs') / filename
    if not filepath.exists():
        return []
    
    with open(filepath, 'r', encoding='utf-8') as file:
        try:
            data = json.load(file)
            return data.get('comments', [])
        except json.JSONDecodeError:
            return []

def merge_comments(existing: List[Dict], new: List[Dict]) -> List[Dict]:
    """Combina comentarios existentes con nuevos, eliminando duplicados y ordenando por fecha"""
    # Crear un conjunto de identificadores únicos (autor + timestamp + mensaje)
    existing_ids = {(c['author'], c['timestamp'], c['message']) for c in existing}
    
    # Filtrar nuevos comentarios que no están ya en los existentes
    unique_new = [c for c in new if (c['author'], c['timestamp'], c['message']) not in existing_ids]
    
    # Combinar y ordenar por timestamp (más nuevos primero)
    merged = existing + unique_new
    merged.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return merged

def save_comments_to_json(comments: List[Dict], filename: str):
    """Guarda los comentarios en un archivo JSON dentro de la carpeta docs/"""
    # Crear la carpeta docs si no existe
    Path('docs').mkdir(exist_ok=True)
    
    filepath = Path('docs') / filename
    data = {
        'comments': [{
            'author': comment['author'],
            'avatar': comment['avatar'],
            'timestamp': comment['timestamp'],
            'comment': comment['message']
        } for comment in comments]
    }
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

def get_comments_from_url(url: str, index: int) -> List[Dict]:
    print(f"Procesando URL {index + 1}: {url}")
    response = requests.get(url)
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    commentsSection = soup.find(class_='commentthread_area')
    
    if not commentsSection:
        print(f"No se encontró la sección de comentarios en la URL {index + 1}")
        return []
    
    comments = extractComments(response.text)
    return comments

def main():
    for i, url in enumerate(urls[:4]):  # Solo procesamos 4 URLs
        try:
            filename = f'comments_{i+1}.json'
            
            # Cargar comentarios existentes
            existing_comments = load_existing_comments(filename)
            
            # Obtener nuevos comentarios
            new_comments = get_comments_from_url(url, i)
            
            # Combinar y guardar
            merged_comments = merge_comments(existing_comments, new_comments)
            save_comments_to_json(merged_comments, filename)
            
            print(f"Comentarios guardados en docs/{filename} ({len(merged_comments)} comentarios totales, {len(new_comments)} nuevos)")
        except Exception as e:
            print(f"Error al procesar la URL {i + 1}: {str(e)}")

if __name__ == '__main__':
    main()