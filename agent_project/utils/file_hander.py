import os,hashlib
from utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader,TextLoader

def get_file_md5_hex(filepath: str): #获得md5的16进制字符串

    if not os.path.exists(filepath):
        logger.error(f"[md5计算]文件{filepath}不存在")
        return

    if not os.path.isfile(filepath):
        logger.error(f"[md5计算]路径{filepath}不是文件")
        return

    md5_obj = hashlib.md5()

    chunk_size = 4096 #文件4kb分片，避免过大
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)
                md5_hex = md5_obj.hexdigest()
                return md5_hex
    except Exception as e:
        logger.error(f"计算为文件{filepath}失败,{str(e)}")
        return None

def listdir_with_allowed_type(path: str, allow_types: tuple[str]): #返回文件夹内的文件列表 tuple:元组
    files = []

    if not os.path.isdir(path):
        logger.error(f"[listdir_with_allowed_type]{path}不是一个文件夹")
        return allow_types

    for f in os.listdir(path):
        if f.endswith(allow_types):
            files.append(os.path.join(path,f))

    return tuple(files)



def txt_loader(filepath: str) -> list[Document]:
    return TextLoader(filepath, encoding="utf-8").load()

def pdf_loader(filepath: str, password=None) -> list[Document]:
    return PyPDFLoader(filepath, password).load()