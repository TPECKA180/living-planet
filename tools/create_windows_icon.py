"""Create the small Windows icon from the checked-in Living Planet artwork."""
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'docs/assets/living-planet-logo.png'
target=ROOT/'docs/assets/living-planet.ico'

def create():
    image=Image.open(source).convert('RGBA')
    # Crop the central living world and keep the full title in the source logo.
    side=750
    left=(image.width-side)//2
    top=0
    icon=image.crop((left,top,left+side,top+side))
    icon.save(target,format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    return target

if __name__=='__main__':
    print(create())
