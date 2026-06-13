# pykrx 호환용 pkg_resources 우회 파일
# Streamlit Cloud에서 pkg_resources / resource_filename 에러 방지

import os
import importlib
from importlib import resources
from importlib.metadata import version, PackageNotFoundError


class Distribution:
    def __init__(self, version_value):
        self.version = version_value


def get_distribution(package_name):
    try:
        return Distribution(version(package_name))
    except PackageNotFoundError:
        return Distribution("0.0.0")


def resource_filename(package_or_requirement, resource_name):
    """
    pykrx가 NanumBarunGothic.ttf 경로를 찾을 때 사용.
    예: resource_filename('pykrx', 'NanumBarunGothic.ttf')
    """
    try:
        return str(resources.files(package_or_requirement).joinpath(resource_name))
    except Exception:
        try:
            pkg = importlib.import_module(package_or_requirement)
            base = os.path.dirname(pkg.__file__)
            return os.path.join(base, resource_name)
        except Exception:
            return resource_name
