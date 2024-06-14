import requests
import json
import time
import configparser
import cv2
import datetime
import subprocess
import re
from pathlib import Path

config = configparser.ConfigParser()

config.read('config.txt')
COMPANY_HOUSE_KEY = config['general']['CompanyHouseKey']
WORK_DIRECTORY = config['general']['Dir']


def send_request_to_companies_house_api(ref):
    """
    This function sends a request to the Companies House API and in case of a JSONDecodeError,
     it waits for 20 seconds and retries. This is done to avoid overloading the API.
    :param ref:
    :return:
    """
    try:
        res = requests.get(ref, headers={'Authorization': COMPANY_HOUSE_KEY}).json()
        return res
    except json.decoder.JSONDecodeError:
        print('...Zzz....', end=' ')
        time.sleep(20)
        return send_request_to_companies_house_api(ref)


def process_currencies_share_price(price_share, date):
    if price_share == 'nil':
        return None
    if '$' in price_share:
        price_share = float(price_share.replace('$', '').replace('us', ''))
        rate = requests.get(
            'https://api.exchangeratesapi.io/{:%Y-%m-%d}?base=USD'.format(date)).json()
        price_share *= rate['rates']['GBP']

    elif '€' in price_share or 'eur' in price_share:
        price_share = float(price_share.replace('€', '').replace('eur', ''))
        rate = requests.get(
            'https://api.exchangeratesapi.io/{:%Y-%m-%d}?base=EUR'.format(date)).json()
        price_share *= rate['rates']['GBP']

    else:
        price_share = float(price_share.replace('£', '').replace('gbp', ''))

    return price_share


def remove_table_borders(image):
    result = image.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # Remove horizontal lines
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    remove_horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    contours = cv2.findContours(remove_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours[0] if len(contours) == 2 else contours[1]
    for c in contours:
        cv2.drawContours(result, [c], -1, (255, 255, 255), 5)

    # Remove vertical lines
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    remove_vertical = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    contours = cv2.findContours(remove_vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours[0] if len(contours) == 2 else contours[1]
    for c in contours:
        cv2.drawContours(result, [c], -1, (255, 255, 255), 5)
    return result


def crop_image(img, cropped_img_path, x0=0, x1=100, y0=0, y1=100, remove_borders=False):
    crop_img = img[
               x0 * img.shape[0] // 100:
               x1 * img.shape[0] // 100,
               y0 * img.shape[1] // 100:
               y1 * img.shape[1] // 100
               ]
    if remove_borders:
        crop_img = remove_table_borders(crop_img)
    cv2.imwrite(cropped_img_path, crop_img)
    return None


def get_text_from_image(doc_path, img_name, psm):
    """
    This function extracts text from an image using tesseract and post-processes it with regex.
    :param img_name: image file name
    :param psm: tesseract page segmentation mode
    :return:
    """
    tesseract_command = 'tesseract {} {} --psm {} --dpi 92'.format(doc_path + 'pages/{}.jpg'.format(img_name),
                                                          doc_path + 'pages/' + img_name, psm)

    subprocess.call(tesseract_command, shell=True)

    with open(doc_path + 'pages/{}.txt'.format(img_name), 'r') as f:
        detected_text = f.read().replace(',', '').replace('-', '').replace('—', '').replace(
            '_', '').replace('!', '').replace('|', '').replace(')', '').lower()
        detected_text = re.sub(r' +', ' ', detected_text)
        detected_text = re.sub(r'(\d) \. (\d)', r'\1.\2', detected_text)
        detected_text = re.sub('pound sterling', '£', detected_text)
        detected_text = re.sub('usd', '\$', detected_text)
        detected_text = re.sub(r'(€|\$|£|eur|gbp) ', r'\1', detected_text)
        detected_text = re.sub(r'\n+', r'\n', detected_text)
    return detected_text


def correct_wrongly_recognized_symbols(text):
    """
    This function corrects wrongly recognized symbols in the text.
    :param text:
    :return:
    """
    replace_dict = {':': '',
                    ' ': '',
                    '/': '7',
                    '§': '5',
                    '|': '',
                    "'": '',
                    '©': '0',
                    '—': ''}
    for replaced_symbol in replace_dict.keys():
        text = text.replace(replaced_symbol, replace_dict[replaced_symbol]).strip()
    return text
