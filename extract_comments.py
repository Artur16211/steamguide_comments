import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import bs4
import requests
import json
import dateparser

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
            while not timestamp.endswith(' '):
                timestamp = timestamp[:-1]
            timestamp = timestamp[:-1]
            date = datetime.strptime(timestamp, '%d %B, %Y @ %I:%M:%S %p')

        result.append(Comment(autor, message, date))
    return result

def save_comments_to_json(comments, filename):
    data = {
        'comments': [{
            'author': comment.autor,
            'message': comment.message,
            'timestamp': comment.timeStamp.isoformat()
        } for comment in comments]
    }
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

def get_comments_from_url(url, index):
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
            comments = get_comments_from_url(url, i)
            filename = f'comments_{i+1}.json'
            save_comments_to_json(comments, filename)
            print(f"Comentarios guardados en {filename} ({len(comments)} comentarios)")
        except Exception as e:
            print(f"Error al procesar la URL {i + 1}: {str(e)}")

if __name__ == '__main__':
    main()