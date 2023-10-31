import tkinter as tk
from tkinter import filedialog
from datetime import datetime

import requests
import pandas as pd
import os
import logging
import yaml

# Set up logging
log_dir = "log"
os.makedirs(log_dir, exist_ok=True)  # Create the log directory if it doesn't exist
log_file_path = os.path.join(log_dir, "wordpress_auto_post.log")

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s: %(message)s',
                    handlers=[logging.FileHandler(log_file_path),
                              logging.StreamHandler()])  # Logging to both file and console

# Load configurations from a YAML file
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USERNAME = config['username']
PASSWORD = config['password']
WP_API_POSTS = config['wp_api_posts']
WP_API_MEDIA = config['wp_api_media']
WP_API_BASE = config['wp_api_base']

def get_or_create_term(taxonomy_slug, term_name):
    headers = {'Content-Type': 'application/json'}
    response = requests.get(f"{WP_API_BASE}/{taxonomy_slug}/?slug={term_name}", headers=headers, auth=(USERNAME, PASSWORD), verify=False)
    
    if response.status_code == 200:
        terms = response.json()
        if terms:
            term_id = terms[0]['id']
        else:
            # Term does not exist, create a new one
            new_term_data = {
                'name': term_name,
                'taxonomy': taxonomy_slug
            }
            response = requests.post(f"{WP_API_BASE}/{taxonomy_slug}", headers=headers, json=new_term_data, auth=(USERNAME, PASSWORD), verify=False)
            if response.status_code == 201:
                term_id = response.json().get('id')
            else:
                logger.error(f"新しいタームの作成中にエラーが発生しました: {taxonomy_slug}, {term_name}. Status code: {response.status_code}")
                term_id = None
    else:
        logger.error(f"タームの取得中にエラーが発生しました: {taxonomy_slug}, {term_name}. Status code: {response.status_code}")
        term_id = None

    return term_id


# Function to upload image and get the media id
def upload_image(image_path):
    try:
        file_name = os.path.basename(image_path)
        auth=(USERNAME, PASSWORD)
        with open(image_path, 'rb') as file:
            response = requests.post(WP_API_MEDIA, auth=(USERNAME, PASSWORD), files={'file': file}, verify=False)
            if response.status_code == 201:
                logger.info(f"アップロードに成功しました: {file_name}")
                return response.json()['id']
            else:
                logger.error(f"アップロードに失敗しました: {file_name}. Status code: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"画像のアップロード中にエラーが発生しました: {e}")
        return None


def get_image_url(media_id):
    try:
        response = requests.get(f"{WP_API_MEDIA}/{media_id}", auth=(USERNAME, PASSWORD), verify=False)
        if response.status_code == 200:
            return response.json().get('source_url')
        else:
            logger.error(f"Media details could not be retrieved. Status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"An error occurred while fetching media details: {e}")
        return None


# Function to create a post
def create_post(row):
    try:
        headers = {'Content-Type': 'application/json'}
        media_id = upload_image(row['image_path'])  # Getting the media ID by uploading the image
        media_url = get_image_url(media_id)
        data = {
            'title': row['title'],
            'content': row['content'],
            'featured_media': media_id,  # Setting the featured_media using the media ID
            'status': row['Status'],
            'author': row['Author ID'],
            'post_type': row['Post Type'],
            'comment_status': row['Comment Status'],
            'meta_field': {
                'image_prompt': row['image_prompt'],
                'image_filename': row['image_filename'],
                'image_prompt': row['image_prompt'],
                'qodef_stock_photography_date_meta': datetime.now().strftime('%Y年%m月%d日'),
                'qodef_stock_photography_licence_meta': row['qodef_stock_photography_licence_meta'],
                'qodef_stock_photography_free_meta': row['qodef_stock_photography_free_meta'],
                'qodef_stock_photography_dl_image_meta': media_url  # Setting the meta to the same media ID
            },
            'stock-photography-category': [get_or_create_term('stock-photography-category', term_name) for term_name in row['Stock Photography Categories'].split(',')],
            'stock-photography-tag': [get_or_create_term('stock-photography-tag', term_name) for term_name in row['Stock Photography Tags'].split(',')]
        }

        response = requests.post(WP_API_POSTS, headers=headers, json=data, auth=(USERNAME, PASSWORD), verify=False)

        if response.status_code == 201:
            logger.info(f"投稿の作成に成功しました: {row['title']}")
        else:
            logger.error(f"投稿の作成に失敗しました: {row['title']}. Status code: {response.status_code}")
    except Exception as e:
        logger.error(f"投稿の作成中にエラーが発生しました: {e}")

def get_csv_file_path():
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    file_path = filedialog.askopenfilename(title="CSVファイルを選択してください", filetypes=(("CSV files", "*.csv"),))
    return file_path

# Reading the CSV file
try:
    CSV_FILE_PATH = get_csv_file_path()  # Get the CSV file path using a file dialog
    if CSV_FILE_PATH:  # If a file was selected
        df = pd.read_csv(CSV_FILE_PATH)
        logger.info(f"CSVファイルの読み込みに成功しました: {CSV_FILE_PATH}")
    else:
        logger.error("CSVファイルが選択されませんでした")
except Exception as e:
    logger.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")

# Processing each row in the CSV file
for index, row in df.iterrows():
    create_post(row)