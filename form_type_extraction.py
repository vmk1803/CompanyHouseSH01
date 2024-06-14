import json
import subprocess
from pathlib import Path
import cv2
import pandas as pd
from datetime import datetime


def determine_form_type_from_text(text, filing_date=None):
    """
    This function determines the specific type of filing based on the text of the document.
    :param text:
    :param filing_date:
    :return:
    """
    if 'electronically filed document' in text.lower():
        if filing_date >= datetime(2014, 1, 1):
            return 'online'
        else:
            return 'online_old'

    if 'version6.0' in text.lower().replace(' ', ''):
        return 'offline6'
    if 'version5.0' in text.lower().replace(' ', ''):
        return 'offline5'
    if 'version4.0' in text.lower().replace(' ', ''):
        return 'offline4'
    return 'unknown'


def determine_form_type(doc_path, filing_date):
    """
    This function determines the type of form based on the text extracted from the document.
    :return:
    """

    with open(doc_path + '/metadata.json', 'r') as f:
        filing_date = pd.to_datetime(json.load(f)['date'])

    if Path(doc_path + 'pages/form_type.txt').is_file():
        with open(doc_path + 'pages/form_type.txt', 'r') as f:
            detected_text = f.read()
        form_type = determine_form_type_from_text(detected_text, filing_date)
        if form_type != 'unknown':
            return form_type

    for page in range(3):
        img = cv2.imread(doc_path + 'pages/{}.jpeg'.format(page))
        if img is None:
            continue
        crop_img = img[8 * img.shape[0] // 10:, :]
        cv2.imwrite(doc_path + 'pages/formtype.jpg', crop_img)
        tesseract_command = 'tesseract {} {} --psm 6'.format(doc_path + 'pages/formtype.jpg',
                                                             doc_path + 'pages/form_type')
        subprocess.call(tesseract_command, shell=True)
        with open(doc_path + 'pages/form_type.txt', 'r') as f:
            detected_text = f.read()
        form_type = determine_form_type_from_text(detected_text, filing_date)
        if form_type != 'unknown':
            return form_type
    return form_type
