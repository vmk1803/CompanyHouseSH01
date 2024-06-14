# -*- coding: utf-8 -*-
import pandas as pd
from pdf2image import convert_from_path
import requests
import subprocess
from pathlib import Path
import json
import configparser
import warnings
from document_parser import DocumentProcessorFactory
from form_type_extraction import determine_form_type
from utils import send_request_to_companies_house_api


def get_filing_history(ch_id):
    """
    This function gets the filing history of a startup given its company house id.
    :param ch_id:
    :return:
    """
    fh_req = 'https://api.companieshouse.gov.uk/company/{}/filing-history?start_index={}&items_per_page=100'
    n_items = 100
    start_index = 0
    sh01_docs = []
    while n_items == 100:
        response = send_request_to_companies_house_api(fh_req.format(ch_id, start_index))
        n_items = len(response.get('items', []))
        start_index += n_items
        sh01_docs.extend([i for i in response.get('items', []) if i.get('type', '') == 'SH01'])
    return sh01_docs


class CompaniesHouseHandler:
    """
    This class handles the interaction with the Companies House API.
    """
    def __init__(self, config_path='config.txt'):
        config = configparser.ConfigParser()
        config.read(config_path)
        self.COMPANY_HOUSE_KEY = config['general']['CompanyHouseKey']
        self.WORK_DIRECTORY = config['general']['Dir']

    def download_document(self, doc_item, ch_id):
        """
        This function downloads a document from the Companies House API and saves it in the WORK_DIRECTORY.
        :param doc_item: item from the filing history
        :param ch_id: company house id
        :return:
        """
        doc_folder_path = self.WORK_DIRECTORY + '/' + ch_id
        if 'links' not in doc_item or 'document_metadata' not in doc_item['links']:
            return
        doc_path = f'{doc_folder_path}/{doc_item["action_date"]}_{doc_item["transaction_id"]}/'
        if Path(doc_path + 'document.pdf').is_file():
            warnings.warn(f'SH01 document {doc_item["transaction_id"]} already downloaded. Download skipped.')
            return

        document_id = doc_item['links']['document_metadata'].split('/')[-1]
        curl_command = f'curl -i -u{self.COMPANY_HOUSE_KEY}: https://document-api.companieshouse.gov.uk/document/{document_id}/content'
        doc_content_res = subprocess.check_output(curl_command, shell=True)
        aws_url = str(doc_content_res).split('Location: ')[-1].split('\\r\\nServer:')[0]
        aws_response = requests.get(aws_url)
        Path(doc_path + 'pages/').mkdir(parents=True, exist_ok=True)

        with open(doc_path + 'metadata.json', 'w') as f:
            json.dump(doc_item, f)

        with open(doc_path + 'document.pdf', 'wb') as f:
            f.write(aws_response.content)

        pages = convert_from_path(doc_path + '/document.pdf', 500, last_page=10)
        for idx, page in enumerate(pages[:10]):
            page.save(f'{doc_path}/pages/{idx}.jpeg', 'JPEG')

    def parse_document(self, doc_item, ch_id):
        """
        This function parses a document using the DocumentProcessor class.
        :param doc_item: document item from the filing history
        :param ch_id: company house id of the startup
        :return:
        """
        doc_folder_path = self.WORK_DIRECTORY + '/' + ch_id
        doc_path = f'{doc_folder_path}/{doc_item["action_date"]}_{doc_item["transaction_id"]}/'
        form_type = determine_form_type(doc_path, pd.to_datetime(doc_item['action_date']))
        try:
            doc_proc = DocumentProcessorFactory.create_processor(form_type, doc_path)
            results = doc_proc.parse_document()
        except ValueError as ve:
            warning_message = f'Error parsing document {doc_item["transaction_id"]}. Error: {ve}'
            warnings.warn(warning_message)
            results = {}
        return results

    def process_ch_id(self, ch_id):
        """
        This function processes a single company house id by getting the filing history,
        downloading and parsing the documents and saving the results.
        :param ch_id:
        :return:
        """
        sh01_docs = get_filing_history(ch_id)
        for doc in sh01_docs:
            self.download_document(doc, ch_id)
            res = self.parse_document(doc, ch_id)
            doc_folder_path = self.WORK_DIRECTORY + '/' + ch_id
            doc_path = f'{doc_folder_path}/{doc["action_date"]}_{doc["transaction_id"]}/'
            with open(doc_path + 'result.json', 'w') as f:
                json.dump(res, f)
        return

    def process_ch_ids_list(self, ch_list_path=None):
        """
        This function processes a list of company house ids by calling process_ch_id for each id.
        :param ch_list_path: file path to the list of company house ids
        :return:
        """
        if ch_list_path is None:
            ch_list_path = self.WORK_DIRECTORY + '/company_house_ids_list'
        with open(ch_list_path, 'r') as f:
            ch_ids = f.readlines()
        ch_ids = [i.replace('\n', '') for i in ch_ids]
        for ch_id in ch_ids:
            self.process_ch_id(ch_id)
        return
