import sys
from pathlib import Path

# DTIALPS.py Slicer disinda da import edilebilir (yerel taban siniflar), bu yuzden
# saf hesap fonksiyonlari duz pytest ile test edilebilir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "DTIALPS"))
