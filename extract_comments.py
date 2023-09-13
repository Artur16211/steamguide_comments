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


def save_comments_to_json(comments):
    data = {
        'comments': comments
    }
    with open('comments.json', 'w') as file:
        json.dump(data, file)


def getAllComments(url=None):
    if url is None:
        url = exampleInputUrl

    response = requests.get(url)
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    commentsSection = soup.find(class_='commentthread_area')
    assert commentsSection, "Cannot find 'commentthread_area' class"

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


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else None
    getAllComments(url)


if __name__ == '__main__':
    main()
