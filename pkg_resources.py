# pykrx 호환용 pkg_resources 우회 파일
# Streamlit Cloud에서 pkg_resources ModuleNotFoundError 방지

from importlib.metadata import version, PackageNotFoundError

class Distribution:
    def __init__(self, version_value):
        self.version = version_value

def get_distribution(package_name):
    try:
        return Distribution(version(package_name))
    except PackageNotFoundError:
        return Distribution("0.0.0")
