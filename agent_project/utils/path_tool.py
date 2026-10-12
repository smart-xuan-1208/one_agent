import os

def get_project_root() -> str:
    #获取项目路径
    current_file = os.path.abspath(__file__)
    #获取项目文件路径
    current_dir = os.path.dirname(current_file)
    #获取项目根目录路径
    project_root = os.path.dirname(current_dir)
    return project_root

#传递相对路径获取绝对路径
def get_abs_path(relative_path: str) -> str:
    project_root = get_project_root()
    abs_path = os.path.join(project_root,relative_path)
    return abs_path