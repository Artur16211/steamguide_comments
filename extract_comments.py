import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import bs4
import requests
import dateparser
import json
import os
from pathlib import Path


# config variables:
exampleInputUrl = 'https://steamcommunity.com/sharedfiles/filedetails/?id=2819323099'
BACKUP_JSON_PATH = 'comments.json'
# end config


_COMMENT_REQUEST_PATTERN = 'https://steamcommunity.com/comment/PublishedFile_Public/render/{owner}/{feature}/'


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

    return _COMMENT_REQUEST_PATTERN.format(owner=ownerMatch.group(1), feature=feature.group(1))


def extractComments(htmlText: str) -> list[Comment]:
    result = []
    bs = bs4.BeautifulSoup(htmlText, "html.parser")
    for singleComment in bs.find_all(class_='commentthread_comment responsive_body_text'):
        autor: str = singleComment.find('bdi').text.strip()
        message: str = singleComment.find(
            class_='commentthread_comment_text').text.strip()
        timestamp: str = singleComment.find(
            class_='commentthread_comment_timestamp')['title'].strip()

        try:
            date = datetime.strptime(timestamp, '%d %B, %Y @ %I:%M:%S %p %Z')
        except ValueError:
            while not timestamp.endswith(' '):  # remove zone
                timestamp = timestamp[:-1]
            timestamp = timestamp[:-1]  # and trailing space
            date = datetime.strptime(timestamp, '%d %B, %Y @ %I:%M:%S %p')

        result.append(Comment(autor, message, date))
    return result


def progressRange(start, stop, step):
    for current in range(start, stop, step):
        print(
            f"Progress: [{current:{len(str(stop))}}/{stop}={current / stop:0.2f}]")
        yield current
    print(f"Progress: [{stop}/{stop}={1.:0.2f}]")


def save_comments_to_json(comments, filepath='comments.json'):
    data = {
        'comments': comments
    }
    # Crear directorio si no existe
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as file:
        json.dump(data, file, indent=2, default=str)


def load_comments_from_json(filepath):
    try:
        with open(filepath, 'r') as file:
            data = json.load(file)
            return data.get('comments', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def combine_comments(new_comments, old_comments_path='comments_old.json'):
    # Cargar comentarios antiguos si el archivo existe
    old_comments = []
    if os.path.exists(old_comments_path):
        old_comments = load_comments_from_json(old_comments_path)
    
    # Combinar los comentarios (nuevos primero, luego los antiguos)
    combined_comments = new_comments + old_comments
    
    # Eliminar duplicados (basado en autor, timestamp y parte del mensaje)
    unique_comments = []
    seen = set()
    for comment in combined_comments:
        # Creamos una clave única basada en autor, timestamp y parte del mensaje
        identifier = (comment.get('author'), 
                     comment.get('timestamp'), 
                     str(comment.get('comment'))[:50])
        if identifier not in seen:
            seen.add(identifier)
            unique_comments.append(comment)
    
    return unique_comments


def getAllComments(url=None):
    if url is None:
        url = exampleInputUrl

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        
        comments_section = soup.find(class_='commentthread_area')
        if not comments_section:
            print("Warning: No se encontró la sección de comentarios en el HTML.")
            return None

        comment_containers = comments_section.find_all(class_='commentthread_comment')
        if not comment_containers:
            print("Warning: No se encontraron contenedores de comentarios.")
            return None

        new_comments = []
        for container in comment_containers:
            try:
                avatar = container.find(class_='commentthread_comment_avatar')
                avatar_img = avatar.find('img')['src'] if avatar else None

                author = container.find(class_='commentthread_comment_author')
                author_name = author.find('bdi').text.strip() if author else "Desconocido"

                timestamp_tag = container.find(class_='commentthread_comment_timestamp')
                timestamp_str = timestamp_tag['title'] if timestamp_tag else None

                timestamp = dateparser.parse(timestamp_str) if timestamp_str else datetime.now()

                comment_text = container.find(class_='commentthread_comment_text')
                comment_text = comment_text.text.strip() if comment_text else ""

                comment = {
                    'author': author_name,
                    'avatar': avatar_img,
                    'timestamp': timestamp.isoformat() if timestamp else datetime.now().isoformat(),
                    'comment': comment_text
                }

                new_comments.append(comment)
            except Exception as e:
                print(f"Error procesando un comentario: {e}")
                continue

        return new_comments

    except Exception as e:
        print(f"Error al obtener comentarios: {e}")
        return None


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Intentar obtener nuevos comentarios
    new_comments = getAllComments(url)
    
    # Cargar comentarios existentes
    current_comments = load_comments_from_json(BACKUP_JSON_PATH)
    
    # Cargar comentarios antiguos
    old_comments = []
    if os.path.exists('comments_old.json'):
        old_comments = load_comments_from_json('comments_old.json')
    
    # Determinar qué comentarios vamos a usar
    if new_comments is not None:
        # Si obtuvimos nuevos comentarios, los combinamos con los antiguos
        all_comments = combine_comments(new_comments, old_comments)
    else:
        # Si no obtuvimos nuevos, combinamos los actuales con los antiguos
        print("Usando archivos locales para combinar comentarios...")
        all_comments = combine_comments(current_comments, old_comments)
    
    # Guardar los comentarios combinados
    save_comments_to_json(all_comments, BACKUP_JSON_PATH)
    
    # Mostrar los comentarios obtenidos
    for comment in all_comments:
        print(f"{comment.get('author')} ({comment.get('timestamp')}): {comment.get('comment')}")
    
    print(f"\nTotal de comentarios: {len(all_comments)}")


if __name__ == '__main__':
    main()