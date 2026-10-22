import zipfile
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "despesas_contratadas_2026_XX.csv"


@pytest.fixture
def zip_path(tmp_path):
    data = FIXTURE.read_bytes()
    brasil = data.replace(b'"RN";', b'"BR";')  # arquivo BRASIL distinguivel pela UF
    path = tmp_path / "teste.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("despesas_contratadas_candidatos_2026_RN.csv", data)
        z.writestr("despesas_contratadas_candidatos_2026_BRASIL.csv", brasil)
        z.writestr("despesas_pagas_candidatos_2026_RN.csv", data)
    return path
