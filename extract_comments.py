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


def save_comments_to_json(new_comments):
    all_comments = new_comments

    try:
        with open('comments_old.json', 'r') as old_file:
            old_data = json.load(old_file)
            if isinstance(old_data, list):
                old_comments = old_data
            elif isinstance(old_data, dict) and 'comments' in old_data:
                old_comments = old_data['comments']
            else:
                old_comments = []
            all_comments += old_comments
    except FileNotFoundError:
        # No old comments to merge
        pass

    data = {
        'comments': all_comments
    }
    with open('comments.json', 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_existing_comments():
    try:
        with open('comments.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            if isinstance(data, dict) and 'comments' in data:
                return data['comments']
            return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []


def getAllComments(url=None):
    if url is None:
        url = exampleInputUrl

    response = requests.get(url)
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    commentsSection = soup.find(class_='commentthread_area')
    
    if not commentsSection:
        print("No se encontró la sección de comentarios, devolviendo comentarios existentes")
        existing_comments = load_existing_comments()
        save_comments_to_json([])  # Esto preservará los comentarios existentes
        return existing_comments

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
            'timestamp': timestamp.isoformat(),
            'comment': comment_text
        }

        comments.append(comment)

    save_comments_to_json(comments)
    return comments


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else None
    comments = getAllComments(url)
    print(f"Se procesaron {len(comments)} comentarios")


if __name__ == '__main__':
    main()