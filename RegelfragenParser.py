#!/usr/bin/env python
# coding: utf-8

import json

from bs4 import BeautifulSoup
import requests
import http
from dataclasses import dataclass
from datetime import date, datetime
import json
from tqdm import tqdm

from typing import List


@dataclass
class Question:
    group_id: int
    question_id: int
    question: str
    answer_index: int
    answer_text: str
    created: date
    last_edited: date
    multiple_choice: List[str]
    
    def toDict(self):
        return {
            "group_id": self.group_id, 
            "question_id": self.question_id, 
            "question": self.question, 
            "answer_index": self.answer_index, 
            "answer_text": self.answer_text, 
            "created": self.created, 
            "last_edited": self.last_edited, 
            "multiple_choice": self.multiple_choice
        }
    
@dataclass
class QuestionGroup:
    id: int
    name: str
    
    def toDict(self):
        return {
            "id": self.id,
            "name": self.name
        }

session = requests.Session()
r = session.get("https://bfv.sr-regeltest.de/users/sign_in")
base_url = "https://bfv.sr-regeltest.de"


login_page = BeautifulSoup(r.content, 'html.parser')
authenticity_token = login_page.find('input', {'name': 'authenticity_token'})['value']

# login

username = input("Benutzername eingeben\n")
password = input("Passwort eingeben\n")

url = 'https://bfv.sr-regeltest.de/users/sign_in'
myobj = {'authenticity_token': authenticity_token,
         'user[email]': username,
         'user[password]': password,
         'user[remember_me]': "0",
         'commit': "Anmelden"}

login_answer = session.post(url, data=myobj)

if 'Passwort ungültig' in login_answer.content.decode():
    print("Falsches Passwort.")
    import sys
    sys.exit(1)


regelfragen_tables = []
for i in range(1, 93):
    response = session.get(f'https://bfv.sr-regeltest.de/questions?page={i}')
    soup = BeautifulSoup(response.content, 'html.parser')
    regelfragen_tables += soup.find("table").find("tbody").findAll("tr")


print(f"{len(regelfragen_tables)} Regelfragen gefunden!")


def parse_regelfragen(soup_filtered, session):
    output_questions = []
    output_questiongroups = {}
    group_25_count = 0
    for element in tqdm(soup_filtered):
        rows = element.findAll("td")
        
        question_url = rows[0].find('a').attrs['href']
        regel_id = rows[0].find('a').contents[0]
        group_name = rows[1].contents[0]
        
        try:
            int(regel_id)
            regel_id = regel_id.zfill(5)
            group_id = int(regel_id[0:2])
            question_id = int(regel_id[2:])

        except ValueError:
            group_25_count += 1
            group_id = 25
            question_id = group_25_count
        
        if group_id not in output_questiongroups:
            output_questiongroups[group_id] = QuestionGroup(group_id, group_name)
        
        detail_page = BeautifulSoup(session.get(base_url + question_url).content, 'html.parser')
        content = detail_page.findAll("div", {"class": "card-body"})
        question = content[0].findAll("p")[1].contents[0].strip()
        if len(content[1].findAll("tr", {"class": "wrong-answer"})) > 0:
            # multiple choice!
            multiple_choice = []
            for i, answers in enumerate(content[1].findAll("tr")):
                multiple_choice_answer = answers.find("td").contents[0].strip()
                if answers["class"][0] == 'correct-answer':
                    answer_index = i
                    answer_text = multiple_choice_answer
                multiple_choice += [answers.find("td").contents[0].strip()]
        else:
            answer_elements = content[1].find("p")
            if answer_elements:
                answer_text = answer_elements.contents[0].strip()
            else:
                answer_text = ""
                print(f"Regelgruppe {group_id} - Regel-ID {question_id} hat eine leere Antwort!")
            multiple_choice = []
            answer_index = -1
        
        output_questions += [
            Question(
                group_id,
                question_id,
                question,
                answer_index,
                answer_text,
                datetime.strptime(rows[3].contents[0], '%d.%m.%Y').date(),
                datetime.strptime(rows[4].contents[0], '%d.%m.%Y').date(),
                multiple_choice,
)]
    return output_questiongroups, output_questions

print("Downloade nun die Regelfragen...")

regelgruppen, regelfragen = parse_regelfragen(regelfragen_tables, session)
regelgruppen_sorted = list(regelgruppen.values())
regelgruppen_sorted = sorted(regelgruppen_sorted, key=lambda x: x.id)

regelgruppen_list = [regelgruppe.toDict() for regelgruppe in regelgruppen_sorted]
regelfragen_list = [regelfrage.toDict() for regelfrage in regelfragen]

print("Speichere die Ausgabe parallel zu dieser Datei als 'question_export.json'")

with open('question_export.json', 'w+') as file:
    json.dump({"question_groups": regelgruppen_list, "questions": regelfragen_list}, file, default=str)