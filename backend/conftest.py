"""
Configuration pytest racine du backend.

Garantit que le package `src` est importable quelle que soit la manière dont
pytest est invoqué. En CI, la commande est `pytest` (et non `python -m pytest`),
qui n'ajoute PAS le répertoire courant à sys.path. Sans cela, les modules de
test échouent à l'import avec « ModuleNotFoundError: No module named 'src' ».

pytest charge automatiquement ce conftest.py (situé à la racine du rootdir)
avant la collecte des tests : l'insertion dans sys.path est donc effective pour
tous les imports `from src...` des modules de test.
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
