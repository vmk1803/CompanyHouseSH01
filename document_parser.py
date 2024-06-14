# -*- coding: utf-8 -*-
import json
import logging
import re
import configparser
from abc import ABC, abstractmethod

import cv2
import pandas as pd

from utils import process_currencies_share_price, correct_wrongly_recognized_symbols, get_text_from_image, crop_image


config = configparser.ConfigParser()


class DocumentProcessorFactory:
    @staticmethod
    def create_processor(form_type, doc_path):
        if form_type == 'online':
            return OnlineFormProcessor(doc_path, form_type)
        elif form_type == 'online_old':
            return OnlineOldFormProcessor(doc_path, form_type)
        elif form_type == 'offline6':
            return Offline6FormProcessor(doc_path, form_type)
        elif form_type == 'offline5':
            return Offline5FormProcessor(doc_path, form_type)
        else:
            raise ValueError(f"Unsupported form type: {form_type}")


class AbstractDocumentProcessor(ABC):
    """
    This class processes a document and extracts the relevant information.
    """

    def __init__(self, doc_path, form_type):
        self.form_type = form_type
        self.doc_path = doc_path
        with open(self.doc_path + '/metadata.json', 'r') as f:
            self.date = pd.to_datetime(json.load(f)['date'])

    @abstractmethod
    def extract_share_price_n_allotted(self) -> (float, float):
        """
        Abstract method to extract the share price and number of shares allotted from a document.
        :return: tuple with share price and number of shares allotted
        """
        raise NotImplementedError

    @abstractmethod
    def extract_total_shares(self) -> int:
        """
        Abstract method to extract the total number of shares from a document.
        :return: total number of shares
        """
        raise NotImplementedError

    def parse_document(self):
        """
        This function parses the document and extracts the relevant information.
        :return: dictionary with the extracted information
        """
        try:
            share_price, n_allotted = self.extract_share_price_n_allotted()
        except Exception as e:
            share_price, n_allotted = None, None
            logging.error(
                f'Error in extracting share price and number of shares at path: {self.doc_path}. Error: {e}')
        try:
            total_shares = self.extract_total_shares()
        except Exception as e:
            total_shares = None
            logging.error(f'Error in extracting total shares at path: {self.doc_path}. Error: {e}')

        if n_allotted is not None and total_shares is not None and share_price is not None:
            fundraising = n_allotted * share_price
            valuation = total_shares * share_price
            if valuation == 0:
                equity = None
            else:
                equity = fundraising / valuation
        else:
            fundraising = None
            valuation = None
            equity = None

        with open(self.doc_path + '/metadata.json', 'r') as f:
            metadata = json.load(f)
            if 'capital' in metadata['description_values']:
                capital = metadata['description_values']['capital'][0]
                capital['figure'] = float(capital['figure'].replace(',', ''))
            else:
                capital = None
            transaction_id = metadata['transaction_id']

        d = {
            'date': self.date.strftime("%Y-%m-%d"),
            'form_type': self.form_type,
            'share_price': share_price,
            'n_allotted': n_allotted,
            'total_shares': total_shares,
            'fundraising': fundraising,
            'valuation': valuation,
            'equity': equity,
            'capital': capital,
            'transaction_id': transaction_id
        }
        return d


class Offline5FormProcessor(AbstractDocumentProcessor):
    def extract_share_price_n_allotted(self) -> (float, float):
        """
        This function extracts the share price and number of shares allotted from an offline form 6.
        :return:
        """
        img = cv2.imread(self.doc_path + 'pages/0.jpeg')
        crop_image(img, self.doc_path + 'pages/{}.jpg'.format('0cropped'), 50, 90, remove_borders=True)

        detected_text = get_text_from_image(self.doc_path, '0cropped', 6)
        detected_text = detected_text.split('currency')[1]
        reg = re.search(r"(\d(\n)?\s?\.?£?\$?€?(\n)?){6}", detected_text)

        # If the regex does not match, try different tesseract psm
        if reg is None:
            detected_text = get_text_from_image(self.doc_path, '0cropped', 11)
            reg = re.search(r"(\d(\n)?\s?\.?£?\$?€?(\n)?){6}", detected_text)
            if reg is None:
                return None, None

        table_line = detected_text[reg.span()[0]:].replace('|', ' ').replace('\\', '')

        price_share = correct_wrongly_recognized_symbols(table_line.split()[2])
        n_allotted = correct_wrongly_recognized_symbols(table_line.split()[0])

        n_allotted = float(n_allotted)

        price_share = process_currencies_share_price(price_share, self.date)

        return price_share, n_allotted

    def extract_total_shares(self) -> float | None:
        """
        This function extracts the total number of shares from an offline form 5.
        :return:
        """
        page_file = self.doc_path + 'pages/{}.jpeg'.format(1)
        img = cv2.imread(page_file)
        crop_image(img, self.doc_path + 'pages/{}.jpg'.format('2cropped'), x1=50)
        detected_text = get_text_from_image(self.doc_path, '2cropped', 4)
        reg = re.search('totals\s?\|?\s?\d\d', detected_text)
        if reg is None:
            logging.error('Error in extracting total shares:{}'.format(detected_text))
            return None
        table_line = detected_text[reg.span()[0] + 6:].replace('|', ' ').replace(',', '')
        try:
            total_shares = float(table_line.split()[0])
            return total_shares
        except ValueError:
            logging.error('Error in extracting total shares:{}'.format(table_line))
            return None


class Offline6FormProcessor(Offline5FormProcessor):
    def extract_total_shares(self) -> float | None:
        """
        This function extracts the total number of shares from an offline form 6.
        :return:
        """

        def extract_from_text(text):
            if 'ist total aggregate' not in text:
                return None
            reg = re.search(r"(\d(\n)?\s?\.?£?\$?€?(\n)?){6}", text)
            if reg is None:
                return None
            table_line = text[reg.span()[0]:].replace('|', ' ')
            total_sh = table_line.split()[0]
            return total_sh

        for page in range(1, 4):
            page_file = self.doc_path + 'pages/{}.jpeg'.format(page)
            img = cv2.imread(page_file)
            crop_image(img, self.doc_path + 'pages/{}.jpg'.format('2cropped'), x0=50, x1=90, remove_borders=True)
        detected_text = get_text_from_image(self.doc_path, '2cropped', 4)
        total_shares = extract_from_text(detected_text)
        if total_shares is not None:
            return total_shares
        return None


class OnlineOldFormProcessor(AbstractDocumentProcessor):

    def extract_share_price_n_allotted(self):
        """
        This function extracts the share price and number of shares allotted from an online form.
        :return:
        """

        img = cv2.imread(self.doc_path + 'pages/0.jpeg')
        crop_image(img, self.doc_path + 'pages/0cropped.jpg', 39, 90)
        detected_text = get_text_from_image(self.doc_path, '0cropped', 6)

        if 'amount paid' not in detected_text.lower():
            return None, None

        price_share = detected_text.lower().split('amount paid')[1].split('\n')[0].strip()
        n_allotted = detected_text.lower().split('number allotted')[1].split('\n')[0].strip()

        price_share = correct_wrongly_recognized_symbols(price_share)
        n_allotted = correct_wrongly_recognized_symbols(n_allotted)

        if '$' in n_allotted:
            n_allotted = n_allotted.replace('$', '8')

        return float(price_share), float(n_allotted)

    def extract_total_shares(self):
        """
        This function extracts the total number of shares from an online old form.
        :return:
        """

        for page in range(1, 10):
            page_file = self.doc_path + 'pages/{}.jpeg'.format(page)
            img = cv2.imread(page_file)
            if img is None:
                continue
            crop_image(img, self.doc_path + 'pages/2cropped.jpg', remove_borders=False)
            detected_text = get_text_from_image(self.doc_path, '2cropped', 4)

            if 'statement of capital (totals)' not in detected_text.lower():
                continue
            try:
                total_shares = (
                    detected_text.lower().split('total number')[1].split('of shares')[0].replace(
                        ':', '').replace('/', '7').replace(
                        '§', '5').replace(' ', '').replace(
                        "'", '').replace('\n', ' '))
            except IndexError:
                logging.error('Error in extracting total shares')
                return None
            return total_shares


class OnlineFormProcessor(OnlineOldFormProcessor):

    def extract_total_shares(self) -> int | None:
        """
        This function extracts the total number of shares from an online form.
        :return:
        """

        def extract_from_text(page_number, doc_path):
            page_file = doc_path + 'pages/{}.jpeg'.format(page_number)
            img = cv2.imread(page_file)
            if img is None:
                return ''
            crop_image(img, doc_path + 'pages/2cropped.jpg', x0=0, x1=50, remove_borders=False)
            text = get_text_from_image(doc_path, '2cropped', 6)
            return text

        for page in range(2, 10):
            detected_text = extract_from_text(page, self.doc_path)
            if 'total number of shares' in detected_text.lower():
                break
        if 'total number of shares' not in detected_text.lower():
            return None
        total_shares = correct_wrongly_recognized_symbols(
            detected_text.lower().split('total number of shares')[1].split('\n')[0])
        return int(total_shares)
