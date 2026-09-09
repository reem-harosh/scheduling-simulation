"""Install the user's source ZIP locally; never adds its contents to Git."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
FILES = {
 '03_Data/Final_Baseline_Calibration.json':'data/calibration/Final_Baseline_Calibration.json',
 '03_Data/rebuild_final_calibration.py':'data/calibration/rebuild_final_calibration.py',
 '03_Data/production_reports.xlsx':'data/sources/production_reports.xlsx',
 '02_Sources/machine_map.drawio':'data/sources/machine_map.drawio',
 '01_Specification/Simulation_World_Specification_v0_3_HE.md':'docs/specification/Simulation_World_Specification_v0_3_HE.md',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',help='Simulation_Project_v0_3.zip')
    args=parser.parse_args()
    staged=[]
    with ZipFile(args.archive) as archive:
        for source,dest in FILES.items():
            content=archive.read('Simulation_Project/'+source)
            path=ROOT/dest
            if path.exists() and path.read_bytes()!=content:
                raise SystemExit(f'Refusing to replace different input: {dest}; keep separate dataset versions')
            staged.append((path,content))
    for path,content in staged:
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_bytes(content)
        print(f'{path.relative_to(ROOT)}  sha256={hashlib.sha256(content).hexdigest()}')
    print('Inputs installed locally. Run: python run_factory.py')

if __name__=='__main__':main()
