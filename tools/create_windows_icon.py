"""Create the small Windows icon from the checked-in Living Planet artwork."""
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'docs/assets/living-planet-logo.png'
target=ROOT/'docs/assets/living-planet.ico'

def create():
    image=Image.open(source).convert('RGBA')
    # The artwork is already square and includes the complete Living Planet
    # wordmark. Keep the whole canvas: a center crop clips the title and crest.
    side=max(image.size)
    if image.size!=(side,side):
        from PIL import ImageOps
        image=ImageOps.contain(image,(side,side),method=Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(side,side),(8,13,18,255))
        canvas.alpha_composite(image,((side-image.width)//2,(side-image.height)//2))
        image=canvas
    icon=image
    icon.save(target,format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    return target

if __name__=='__main__':
    print(create())
