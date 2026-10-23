from pathlib import Path
from equinox_forge.demo_builder import build_demo
from equinox_forge.io import save_document
out=Path(__file__).with_name("german_demo.eqir.json")
save_document(build_demo(),out)
print(out)
