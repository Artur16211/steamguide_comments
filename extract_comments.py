import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import bs4
import requests
from datetime import datetime
import dateparser
import json
import os


# config variables:
exampleInputUrl = 'https://steamcommunity.com/sharedfiles/filedetails/?id=2819323099'
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


def load_comments_from_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
            if isinstance(data, dict) and 'comments' in data:
                return data['comments']
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_comments_to_json(new_comments):
    # Cargar comentarios existentes de ambos archivos
    old_comments = load_comments_from_file('comments_old.json')
    existing_comments = load_comments_from_file('comments.json')
    
    # Combinar todos los comentarios (nuevos + existentes + old)
    all_comments = new_comments + existing_comments + old_comments
    
    # Eliminar duplicados (opcional, puedes implementar lógica según tus necesidades)
    unique_comments = []
    seen = set()
    for comment in all_comments:
        # Creamos una tupla con los datos clave para identificar duplicados
        comment_key = (comment.get('author'), comment.get('comment'), comment.get('timestamp'))
        if comment_key not in seen:
            seen.add(comment_key)
            unique_comments.append(comment)
    
    data = {
        'comments': unique_comments
    }
    with open('comments.json', 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def getAllComments(url=None):
    if url is None:
        url = exampleInputUrl

    try:
        response = requests.get(url)
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        commentsSection = soup.find(class_='commentthread_area')
        
        if not commentsSection:
            print("No se encontró la sección de comentarios, devolviendo comentarios existentes combinados")
            return load_comments_from_file('comments.json') + load_comments_from_file('comments_old.json')

        commentContainers = commentsSection.find_all(
            class_='commentthread_comment')

        comments = []
        for container in commentContainers:
            avatar = container.find(class_='commentthread_comment_avatar')
            avatar_img = avatar.find('img')['src']

            author = container.find(class_='commentthread_comment_author')
            author_name = author.find('bdi').text.strip()

            timestamp_tag = container.find(
                class_='commentthread_comment_timestamp')
            timestamp_str = timestamp_tag['title']

            # Use dateparser to parse the timestamp
            timestamp = dateparser.parse(timestamp_str)

            comment_text = container.find(
                class_='commentthread_comment_text').text.strip()

            comment = {
                'author': author_name,
                'avatar': avatar_img,
                'timestamp': timestamp.isoformat() if timestamp else None,
                'comment': comment_text
            }

            comments.append(comment)

        save_comments_to_json(comments)
        return comments

    except Exception as e:
        print(f"Error al obtener comentarios: {e}")
        print("Devolviendo comentarios existentes combinados")
        return load_comments_from_file('comments.json') + load_comments_from_file('comments_old.json')


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else None
    comments = getAllComments(url)
    print(f"Total de comentarios obtenidos: {len(comments)}")


if __name__ == '__main__':
    main()