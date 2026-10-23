#!/usr/bin/env python3
"""Rebuild the review and platform package from vector sources, never stale PNGs.

Uses only requirements.txt and the standard library. --check builds a fresh
package and compares every byte, including the inventory and source digests.
Native platform installation is intentionally outside this command's scope.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
import product_icon as P
import render as R
import review_product_icon as Review

OUTPUT = ROOT / 'assets/anamorph'
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = tuple(n for n in SIZES if n <= 256)
ICONSET = ((16, 1), (16, 2), (32, 1), (32, 2), (128, 1),
           (128, 2), (256, 1), (256, 2), (512, 1), (512, 2))
SOURCE_FILES = ('design/anamorph.json', 'design/baseline.json', 'design/apple-research.json',
                'design/final-review.json', 'tools/review_product_icon.py',
                'src/product_icon.py', 'src/build_svg.py', 'src/params.json',
                'tools/export_product_icon.py', 'tools/render.py', 'requirements.txt')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def png_bytes(image):
    image = image.copy()
    if image.mode == 'RGBA':
        a = np.array(image)
        a[a[:, :, 3] == 0, :3] = 0  # no hidden coloured matte outside the enclosure
        image = Image.fromarray(a)
    info = PngImagePlugin.PngInfo()
    info.add(b'sRGB', b'\x00')
    out = io.BytesIO()
    image.save(out, format='PNG', pnginfo=info, compress_level=9)
    return out.getvalue()


def complete_icns(pillow_container, rasters):
    """Keep Pillow's standard ICNS entries and supply its omitted small slots.

    icp4/icp5/icp6 are standard 16/32/64 PNG elements, understood by Pillow's
    independent decoder. Rebuild the standard TOC/lengths and use our tagged
    PNG bytes verbatim, so no frame is silently resized or loses its sRGB tag.
    This is container packaging, not a native macOS validation claim.
    """
    entries=[];offset=8
    while offset<len(pillow_container):
        kind=pillow_container[offset:offset+4]
        length=struct.unpack_from('>I',pillow_container,offset+4)[0]
        if kind!=b'TOC ':
            data=pillow_container[offset+8:offset+length]
            size=Image.open(io.BytesIO(data)).width
            entries.append((kind,rasters[size]))
        offset+=length
    entries.extend((kind,rasters[n]) for kind,n in ((b'icp4',16),(b'icp5',32),(b'icp6',64)))
    blocks=[kind+struct.pack('>I',len(data)+8)+data for kind,data in entries]
    toc=b''.join(block[:8] for block in blocks)
    payload=b'TOC '+struct.pack('>I',len(toc)+8)+toc+b''.join(blocks)
    return b'icns'+struct.pack('>I',len(payload)+8)+payload


class Package:
    def __init__(self, output):
        self.output = output
        self.records = []
        self.renders = {}

    def put(self, path, data, target, *, dimensions=None, variant='selected', status='structurally validated', color='sRGB', transparency=None):
        path = Path(path)
        dest = self.output / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            data = data.encode('utf-8')
        dest.write_bytes(data)
        suffix = path.suffix[1:].upper()
        alpha = transparency
        if suffix == 'PNG':
            im = Image.open(io.BytesIO(data))
            dimensions = list(im.size)
            alpha = im.mode == 'RGBA' and im.getextrema()[3][0] < 255
        self.records.append({'path': path.as_posix(), 'format': suffix, 'dimensions': dimensions,
                             'transparency': alpha, 'color_space': color,
                             'target': target, 'variant': variant, 'validation': status,
                             'sha256': digest(data), 'bytes': len(data)})

    def raster(self, svg, size):
        key = (digest(svg.encode()), size)
        if key not in self.renders:
            self.renders[key] = png_bytes(Image.open(io.BytesIO(R.render_resvg_string(svg, size))).convert('RGBA'))
        return self.renders[key]

    def image(self, svg, size):
        return Image.open(io.BytesIO(self.raster(svg, size))).convert('RGBA')


def label_font(size=16):
    # Pillow's bundled font avoids depending on an installed system font.
    return ImageFont.load_default(size=size)


def paste_icon(sheet, icon, x, y):
    sheet.paste(icon, (x, y), icon)


def make_previews(package, config, historical, candidates, selected, small, apple):
    originals = (ROOT / 'reconstruction.svg').read_text()
    designs = [('Historical', originals), ('Square baseline', candidates['square-baseline']),
               ('A / conservative', candidates['A']), ('B / optical', candidates['B']),
               ('C / glass study', candidates['C']), ('Recommended / ' + config['selected'], selected)]
    for size in (1024, 512):
        width = size + 32
        for theme,bg,fg in [('dark','#171e28','#e6edf5'),('light','#e7eaf0','#152030')]:
            sheet = Image.new('RGB', (width * len(designs), size + 100), bg)
            draw = ImageDraw.Draw(sheet)
            for i, (name, svg) in enumerate(designs):
                draw.text((i * width + 16, 16), name, font=label_font(18), fill=fg)
                paste_icon(sheet, package.image(svg, size), i * width + 16, 64)
            suffix='-light' if theme=='light' else ''
            package.put(f'previews/comparison-{size}{suffix}.png', png_bytes(sheet),
                        f'Review: all designs at native {size} px on {theme} desktop', variant='comparison')

    for theme, bg, fg in [('light', '#e7eaf0', '#152030'), ('dark', '#121823', '#e6edf5')]:
        for size in (128, 64, 32, 16):
            cell = max(180, size + 48)
            sheet = Image.new('RGB', (cell * len(designs), size + 100), bg)
            draw = ImageDraw.Draw(sheet)
            for i, (name, svg) in enumerate(designs):
                draw.text((i * cell + 12, 16), name, font=label_font(12), fill=fg)
                # Comparisons always use the same master treatment and size.
                # The selected small optical variant is shown separately.
                paste_icon(sheet, package.image(svg, size), i * cell + (cell-size)//2, 60)
            package.put(f'previews/comparison-{size}-{theme}.png', png_bytes(sheet),
                        f'Review: native {size} px on {theme} desktop', variant='comparison')

    sheet = Image.new('RGB', (1140, 2300), '#171e28')
    draw = ImageDraw.Draw(sheet)
    draw.text((28, 20), f'Selected {config["selected"]} / native pixel sizes / open at 100%', font=label_font(20), fill='white')
    y = 60
    for size in (1024, 512, 256, 128, 64, 48, 32, 24, 16):
        draw.text((16, y + 4), str(size), font=label_font(12), fill='#b8c9d9')
        paste_icon(sheet, package.image(small if size <= config['small']['maximum_size'] else selected, size), 86, y)
        y += size + 10
    package.put('previews/selected-size-ladder.png', png_bytes(sheet), 'Review: selected master and small variant at native sizes', variant='comparison')

    sheet = Image.new('RGB', (1200, 380), '#e7eaf0')
    draw = ImageDraw.Draw(sheet)
    for row, (name, svg) in enumerate([('Master downscale', selected), ('Optical export <=32', small)]):
        draw.text((18, 24 + row*175), name, font=label_font(16), fill='#152030')
        x = 230
        for size in (16, 20, 24, 32):
            draw.text((x, 24 + row*175), str(size), font=label_font(13), fill='#152030')
            paste_icon(sheet, package.image(svg, size), x, 60 + row*175)
            x += 110
    package.put('previews/small-optical-comparison.png', png_bytes(sheet), 'Review: same geometry with reduced glow/rays and stronger curve cores', variant='comparison')

    # This is a labelled mathematical enclosure study, not a Liquid Glass render.
    shape_svg = P.svg_document(f'<clipPath id="study"><path d="{P.body_path(config, True)}"/></clipPath>',
                               '<g clip-path="url(#study)">' + apple.split('</defs>\n', 1)[1].rsplit('</svg>', 1)[0] + '</g>',
                               'Approximate Apple enclosure study')
    # Include all definitions used by the square artwork.
    shape_svg = shape_svg.replace('<defs>\n', '<defs>\n' + apple.split('<defs>\n', 1)[1].split('</defs>', 1)[0])
    sheet = Image.new('RGB', (1120, 620), '#e7eaf0')
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 14), 'Independent rounded composition', font=label_font(18), fill='#152030')
    draw.text((576, 14), 'Apple contour approximation / no native effects', font=label_font(16), fill='#152030')
    paste_icon(sheet, package.image(selected, 512), 24, 64)
    paste_icon(sheet, package.image(shape_svg, 512), 576, 64)
    package.put('previews/masking-comparison.png', png_bytes(sheet), 'Review: approximate system enclosure versus precomposed icon; native mask pending', variant='comparison')

    sheet = Image.new('RGB', (1120, 620), '#171e28')
    draw = ImageDraw.Draw(sheet)
    for i, (name, svg) in enumerate([('Historical / 885 x 957 frame', originals), (f'Recommended {config["selected"]} / 960 x 960 body', selected)]):
        draw.text((i*552+24, 18), name, font=label_font(20), fill='white')
        paste_icon(sheet, package.image(svg, 512), i*552+24, 68)
    package.put('previews/before-after.png', png_bytes(sheet), 'Review and release/documentation illustration', variant='comparison')

    sheet=Image.new('RGB',(1140,440),'#e7eaf0');draw=ImageDraw.Draw(sheet)
    for i,(name,n) in enumerate([('Circular corner / n=2',2),('Utility alternative / n=2.45',2.45),('Template study / n=2.61',2.61)]):
        study=copy.deepcopy(config);study['body']['exponent']=n
        svg=P.svg_document('',f'<path d="{P.body_path(study)}" fill="#0b1826"/>','Independent corner study')
        draw.text((i*380+16,16),name,font=label_font(16),fill='#152030')
        paste_icon(sheet,package.image(svg,352),i*380+14,64)
    package.put('previews/corner-study.png',png_bytes(sheet),'Review: equal square bounds/radius, alternative corner curvature; not a system mask',variant='comparison')

    parts=[P.build_apple_layer(config,historical,name).split('</defs>\n',1)[1].rsplit('</svg>',1)[0]
           for name in ('left','right','interaction')]
    flat=P.svg_document('', '<rect width="1024" height="1024" fill="'+
                        config['candidates'][config['selected']]['background'][0]+'"/>'+''.join(parts),
                        'Unmasked Icon Composer source layers / NO native effects')
    sheet=Image.new('RGB',(900,624),'#e7eaf0');draw=ImageDraw.Draw(sheet)
    draw.text((16,12),'Unmasked source layers / flat background / NO native effects',font=label_font(18),fill='#152030')
    x=16
    for n in (16,32,128,512):
        draw.text((x,48),str(n)+' px',font=label_font(12),fill='#152030')
        paste_icon(sheet,package.image(flat,n),x,80);x+=n+32
    package.put('previews/apple-layers-flat.png',png_bytes(sheet),'Review: actual native SVG foreground geometry without masking or system material; native effects pending',variant='comparison')


def build_package(output):
    config, historical = P.load_design()
    sources = {path:digest((ROOT/path).read_bytes()) for path in SOURCE_FILES}
    p = Package(output)
    candidates = {}
    for name in config['candidates']:
        svg = P.build_product(config, historical, name)
        candidates[name] = svg
        p.put(f'previews/candidates/{name}.svg', svg, 'Editable alternative for owner review', dimensions=[1024,1024], variant=name, transparency=True)
        p.put(f'previews/candidates/{name}-1024.png', p.raster(svg, 1024), 'Full-resolution candidate review', variant=name)
    selected = candidates[config['selected']]
    small = P.build_product(config, historical, small=True)
    opaque = P.build_product(config, historical, variant='opaque')
    apple = P.build_product(config, historical, variant='apple-square')
    for name, svg, target in [('anamorph.svg', selected, 'Canonical independent product master'),
                              ('anamorph-small.svg', small, '16–32 px optical master'),
                              ('anamorph-opaque.svg', opaque, 'Opaque precomposed square for imagery'),
                              ('anamorph-apple-square.svg', apple, 'Unmasked full-bleed flat fallback; not layered native source')]:
        p.put('master/' + name, svg, target, dimensions=[1024,1024],
              variant='small' if name=='anamorph-small.svg' else 'selected',
              transparency=name in ('anamorph.svg','anamorph-small.svg'))
    for name, svg in [('anamorph-rounded-1024', selected), ('anamorph-opaque-1024', opaque), ('anamorph-square-1024', apple)]:
        p.put('master/' + name + '.png', p.raster(svg, 1024), 'Vector-derived 1024 px master raster')

    rasters = {}
    for size in SIZES:
        is_small = size <= config['small']['maximum_size']
        data = p.raster(small if is_small else selected, size)
        rasters[size] = data
        p.put(f'portable/png/anamorph-{size}.png', data, 'Portable imagery / cross-platform icon input',
              variant='small' if is_small else 'selected')

    for logical, scale in ICONSET:
        suffix = '@2x' if scale == 2 else ''
        size = logical * scale
        p.put(f'macos/Anamorph.iconset/icon_{logical}x{logical}{suffix}.png', rasters[size],
              f'macOS conventional iconset: {logical} pt at {scale}x')
    images = {n: Image.open(io.BytesIO(data)).convert('RGBA') for n, data in rasters.items()}
    stream = io.BytesIO()
    images[1024].save(stream, format='ICNS', append_images=[images[n] for n in (32,64,128,256,512)])
    p.put('macos/Anamorph.icns', complete_icns(stream.getvalue(),rasters), 'Finder/Dock/bundle conventional fallback',
          dimensions=[16,32,64,128,256,512,1024], color='sRGB tagged PNG frames',
          status='Pillow decode and chunk validation; macOS iconutil/Finder pending', transparency=True)
    stream = io.BytesIO()
    images[256].save(stream, format='ICO', sizes=[(n,n) for n in ICO_SIZES],
                     append_images=[images[n] for n in ICO_SIZES if n != 256])
    p.put('windows/Anamorph.ico', stream.getvalue(), 'EXE / Explorer / Start Menu / Taskbar / Inno Setup SetupIconFile',
          dimensions=list(ICO_SIZES), color='sRGB source samples; embedded PNG frames untagged',
          status='Directory entries/pixels validated; Anamorph #172 Setup/uninstaller resources and disposable-VM installation passed; Explorer/DPI pending', transparency=True)

    for size in (16,24,32,48,64,128,256,512):
        p.put(f'linux/hicolor/{size}x{size}/apps/tech.rolly.anamorph.png', rasters[size],
              'Freedesktop icon theme / launcher')
    p.put('linux/hicolor/scalable/apps/tech.rolly.anamorph.svg', selected,
          'Freedesktop scalable icon', dimensions=[1024,1024], transparency=True)
    p.put('linux/tech.rolly.anamorph.desktop',
          '[Desktop Entry]\nType=Application\nName=Anamorph\nComment=Stereo image toolkit\n'
          'Exec=Anamorph\nIcon=tech.rolly.anamorph\nTerminal=false\nCategories=AudioVideo;Audio;\n',
          'Future launcher template; executable must be installed on PATH', color='n/a',
          status='desktop-file-validate checked separately; not installed')

    layers = []
    for index, name in enumerate(('left','right','interaction'), 1):
        path = f'apple/layers/{index:02d}-{name}.svg'
        p.put(path, P.build_apple_layer(config, historical, name), 'Icon Composer foreground import',
              dimensions=[1024,1024], status='SVG structure validated; native import/materials pending', transparency=True)
        layers.append(path)
    composer = {'status':'prepared sources, NOT a validated .icon project', 'canvas':[1024,1024],
                'background':{'configure_in_composer':True, 'opaque':True,
                              'gradient_colors':config['candidates'][config['selected']]['background']},
                'foreground_back_to_front':layers,
                'source_effects':'No masking, blur, shadows, opacity or baked system specular effects.',
                'appearances':json.loads((ROOT/'design/apple-research.json').read_text())['appearances'],
                'next_step':'Import in Icon Composer on macOS, tune and inspect all six appearances, save genuine .icon, validate with Xcode.'}
    p.put('apple/import-manifest.json', json.dumps(composer, indent=2)+'\n',
          'Human-readable import handoff; not an Apple project format', color='n/a')
    p.put('apple/Assets.xcassets/Contents.json', '{"info":{"author":"xcode","version":1}}\n',
          'Optional current iOS flat fallback asset catalog', color='n/a', status='JSON validated; actool pending')
    p.put('apple/Assets.xcassets/AppIcon.appiconset/Contents.json',
          json.dumps({'images':[{'filename':'Anamorph-1024.png','idiom':'universal','platform':'ios','size':'1024x1024'}],
                      'info':{'author':'xcode','version':1}}, indent=2)+'\n',
          'Optional current iOS flat fallback asset catalog', color='n/a', status='JSON validated; actool pending')
    # App Store/asset-catalog fallback is unmasked, opaque RGB, never rounded alpha.
    p.put('apple/Assets.xcassets/AppIcon.appiconset/Anamorph-1024.png',
          png_bytes(Image.open(io.BytesIO(p.raster(apple,1024))).convert('RGB')),
          'Optional iOS 1024 px flat fallback; Anamorph currently has no iOS target', status='Opaque RGB/sRGB validated; actool pending')

    make_previews(p, config, historical, candidates, selected, small, apple)
    Review.make_review(p, P, config, historical, selected, small, apple, png_bytes)
    if sources != {path:digest((ROOT/path).read_bytes()) for path in SOURCE_FILES}:
        raise RuntimeError('Source files changed during export; rerun from a settled design state')
    manifest = {'schema_version':1, 'selected_candidate':config['selected'],
                'source_base_commit':json.loads((ROOT/'design/baseline.json').read_text())['original_main'],
                'source_revision':digest(json.dumps(sources,sort_keys=True).encode()),
                'source_files_sha256':sources,
                'dependencies':{name:importlib.metadata.version(name) for name in ('resvg-py','numpy','pillow')},
                'raster_policy':'Direct vector render at each size; small optical source only at <=32 px.',
                'native_platform_validation':'B0 owner-approved; Anamorph JUCE/Windows integration merged; native shell/Composer validation pending; see docs/PRODUCT_ICON_ENGINEERING.md',
                'assets':sorted(p.records,key=lambda r:r['path'])}
    dest=output/'manifests';dest.mkdir(parents=True,exist_ok=True)
    (dest/'assets.json').write_text(json.dumps(manifest,indent=2)+'\n')
    rows=['# Generated asset inventory', '',
          'Rebuild with `python tools/export_product_icon.py`. All dimensions are pixels unless noted. '
          'B0 is owner-approved; Anamorph JUCE/Windows integration is merged. Native shell/Composer validation remains pending; see `docs/PRODUCT_ICON_ENGINEERING.md`. `assets.json` records every content digest. '
          'The inventory and digest index exclude themselves to avoid circular hashes.', '',
          '| Path | Format | Dimensions | Alpha | Color space | Target | Validation |',
          '|---|---|---|---|---|---|---|']
    for r in manifest['assets']:
        dims=str(r['dimensions']) if r['dimensions'] else 'n/a'
        alpha='yes' if r['transparency'] is True else 'no' if r['transparency'] is False else 'format/source dependent'
        rows.append(f"| `{r['path']}` | {r['format']} | {dims} | {alpha} | {r['color_space']} | {r['target']} | {r['validation']} |")
    (dest/'ASSET_MATRIX.md').write_text('\n'.join(rows)+'\n')
    return manifest


def tree_bytes(root):
    return {p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=OUTPUT)
    ap.add_argument('--check',action='store_true',help='Rebuild in isolation and compare all generated bytes')
    args=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='anamorph-product-') as td:
        staging=Path(td)/'package';staging.mkdir()
        manifest=build_package(staging)
        fresh=tree_bytes(staging)
        if args.check:
            current=tree_bytes(args.out)
            changed=sorted(k for k in fresh.keys()|current.keys() if fresh.get(k)!=current.get(k))
            if changed:
                raise SystemExit('Product package differs: '+', '.join(changed))
            print(f'Product package reproducible: {len(fresh)} files; {manifest["source_revision"]}')
        else:
            args.out.mkdir(parents=True,exist_ok=True)
            stale=set(tree_bytes(args.out))-set(fresh)
            if stale:
                raise SystemExit('Review and remove stale generated files before exporting: '+', '.join(sorted(stale)))
            shutil.copytree(staging,args.out,dirs_exist_ok=True)
            print(f'Exported {len(fresh)} files to {args.out}; candidate {manifest["selected_candidate"]}')


if __name__=='__main__':
    main()
