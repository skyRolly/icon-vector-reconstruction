#!/usr/bin/env python3
"""Product/export checks, deliberately separate from reference-image fidelity.

--cross-renderer runs an independent Inkscape or Chromium check. A selected
but broken renderer fails; an absent optional renderer is reported as skipped.
--report writes measured diagnostics without altering generated artwork.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
import build_svg
import product_icon as P
import render as R
from export_product_icon import OUTPUT, SIZES, ICO_SIZES, ICONSET, digest, tree_bytes


def image_rgba(path):
    return np.asarray(Image.open(path).convert('RGBA'))


def black_rgb(path):
    a = image_rgba(path).astype(float)
    return a[:,:,:3] * a[:,:,3:] / 255


def diagnostics(path):
    rgb = black_rgb(path)
    lum = rgb @ np.array([0.2126,0.7152,0.0722])
    weight = np.maximum(lum-20, 0)
    yy,xx = np.indices(lum.shape)
    n = lum.shape[0]
    bright = lum > 160
    # Oklab in D65/sRGB; evaluate the optical midtones outside the flare.
    srgb = rgb / 255
    linear = np.where(srgb <= .04045, srgb/12.92, ((srgb+.055)/1.055)**2.4)
    m1 = np.array([[.4122214708,.5363325363,.0514459929],
                   [.2119034982,.6806995451,.1073969566],
                   [.0883024619,.2817188376,.6299787005]])
    m2 = np.array([[.2104542553,.7936177850,-.0040720468],
                   [1.9779984951,-2.4285922050,.4505937099],
                   [.0259040371,.7827717662,-.8086757660]])
    lab = np.cbrt(linear @ m1.T) @ m2.T
    mask = (lum > 35) & (lum < 150) & ((xx-n/2)**2+(yy-n/2)**2 > (n*.075)**2)
    avg = lab[mask].mean(0)
    return {'luminous_centroid_px':[round(float((xx*weight).sum()/weight.sum()),3),
                                      round(float((yy*weight).sum()/weight.sum()),3)],
            'light_left_fraction':round(float(weight[:,:n//2].sum()/weight.sum()),5),
            'light_top_fraction':round(float(weight[:n//2].sum()/weight.sum()),5),
            'all_channels_ge_250_pixels':int((rgb.min(2)>=250).sum()),
            'any_channel_ge_250_pixels':int((rgb.max(2)>=250).sum()),
            'luminance_gt_160_pixels':int(bright.sum()),
            'optical_midtone_oklab_mean':[round(float(x),5) for x in avg],
            'optical_midtone_oklch_hue_degrees':round(math.degrees(math.atan2(avg[2],avg[1]))%360,2),
            'optical_midtone_oklch_chroma':round(float(np.hypot(avg[1],avg[2])),5),
            'sample_policy':'Luminance 35..150, outside central radius 7.5% of canvas; sRGB D65 Oklab.'}


def geometry_diagnostics():
    config,h=P.load_design();fr=h['frame']
    width,height=fr['right']-fr['left'],fr['bottom']-fr['top']
    a=math.radians(fr['corner_blend_deg'])
    run=fr['corner_r_blend']*(math.sin(a)+1-math.cos(a))+fr['corner_r_main']*(math.cos(a)-math.sin(a))
    points=[point for side in ('left','right') for segment in h['geometry']['arc_'+side]['cubics'][side] for point in segment]
    xs,ys=zip(*points)
    body=config['canvas']-2*config['body']['inset']
    return {'historical':{'canvas':[1024,1024],'frame_centerline_dimensions':[width,height],
                           'frame_height_over_width':height/width,
                           'frame_stroke_envelope':[width+fr['stroke_width'],height+fr['stroke_width']],
                           'margins_left_right_top_bottom':[fr['left'],1024-fr['right'],fr['top'],1024-fr['bottom']],
                           'corner_tangent_run':run,
                           'top_corner_tangent_points':[[fr['left']+run,fr['top']],[fr['right']-run,fr['top']]],
                           'bottom_corner_tangent_points':[[fr['left']+run,fr['bottom']],[fr['right']-run,fr['bottom']]],
                           'nominal_curve_bounds':[min(xs),min(ys),max(xs),max(ys)],
                           'nominal_curve_height_over_width':(max(ys)-min(ys))/(max(xs)-min(xs)),
                           'frame_center':[(fr['left']+fr['right'])/2,(fr['top']+fr['bottom'])/2]},
            'product':{'canvas':[1024,1024],'body_dimensions':[body,body],
                       'body_height_over_width':1,'margins':[config['body']['inset']]*4,
                       'motif_transform':P.motif_transform(config),
                       'curves_scaled_uniformly':True,'flare_anchor_retains_original_right_bias':True}}


class ProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config,cls.historical=P.load_design()
        cls.baseline=json.loads((ROOT/'design/baseline.json').read_text())
        cls.manifest=json.loads((OUTPUT/'manifests/assets.json').read_text())

    def test_01_historical_tree_is_protected(self):
        # Keep the original requirements digest as historical provenance, but
        # allow active dependency pins to change. The generated asset manifest
        # records the current requirements digest and installed versions;
        # export_product_icon.py --check verifies the resulting package bytes.
        changed=[p for p,h in self.baseline['historical_files_sha256'].items()
                 if p!='requirements.txt' and
                 (not (ROOT/p).is_file() or digest((ROOT/p).read_bytes())!=h)]
        self.assertEqual(changed,[], 'Historical files must stay unchanged')
        rebuilt=build_svg.build(self.historical).encode()
        self.assertEqual(rebuilt,(ROOT/'reconstruction.svg').read_bytes())

    def test_02_independent_deterministic_vectors(self):
        for candidate in self.config['candidates']:
            a=P.build_product(self.config,self.historical,candidate)
            b=P.build_product(self.config,self.historical,candidate)
            self.assertEqual(a,b)
            self.assertEqual(a,(OUTPUT/f'previews/candidates/{candidate}.svg').read_text())
        self.assertEqual((OUTPUT/'master/anamorph.svg').read_bytes(),
                         (OUTPUT/f'previews/candidates/{self.config["selected"]}.svg').read_bytes())

    def test_03_every_svg_has_valid_references(self):
        for path in OUTPUT.rglob('*.svg'):
            raw=path.read_text();root=ET.fromstring(raw)
            self.assertEqual(root.get('viewBox'),'0 0 1024 1024',str(path))
            self.assertEqual((root.get('width'),root.get('height')),('1024','1024'))
            ids=[el.get('id') for el in root.iter() if el.get('id')]
            self.assertEqual(len(ids),len(set(ids)),str(path))
            refs=re.findall(r'url\(#([^\)]+)\)',raw)+re.findall(r'href="#([^"]+)"',raw)
            self.assertFalse(set(refs)-set(ids),str(path))
            self.assertNotRegex(raw,r'data:|<image\b|<foreignObject\b|<script\b|https?://(?!www.w3.org/)')

    def test_04_geometric_body_is_square_without_affine_stretch(self):
        b=self.config['body'];s=self.config['canvas']-2*b['inset']
        self.assertEqual(s,960)
        self.assertGreater(b['radius'],0)
        raw=P.build_product(self.config,self.historical)
        self.assertIn(P.body_path(self.config),raw)
        # One uniform scale argument; all historical Béziers/radials stay intact.
        self.assertRegex(P.motif_transform(self.config),r'scale\([0-9.]+\)$')
        self.assertEqual(self.historical['geometry'],json.loads((ROOT/'src/params.json').read_text())['geometry'])

    def test_05_manifest_exhaustive_and_source_current(self):
        recorded={a['path']:a['sha256'] for a in self.manifest['assets']}
        actual=tree_bytes(OUTPUT)
        actual.pop('manifests/assets.json');actual.pop('manifests/ASSET_MATRIX.md')
        self.assertEqual(actual,recorded)
        sources=self.manifest['source_files_sha256']
        for p,h in sources.items():self.assertEqual(digest((ROOT/p).read_bytes()),h,p)
        self.assertEqual(digest(json.dumps(sources,sort_keys=True).encode()),self.manifest['source_revision'])
        self.assertEqual(self.manifest['selected_candidate'],self.config['selected'])

    def test_06_all_png_dimensions_and_srgb_tags(self):
        for record in self.manifest['assets']:
            if record['format']!='PNG':continue
            path=OUTPUT/record['path'];im=Image.open(path)
            self.assertEqual(im.format,'PNG',str(path))
            self.assertTrue(path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertEqual(list(im.size),record['dimensions'],str(path))
            self.assertEqual(im.info.get('srgb'),0,str(path))
            self.assertNotIn('icc_profile',im.info)
            im.verify()
        for n in SIZES:
            self.assertEqual(Image.open(OUTPUT/f'portable/png/anamorph-{n}.png').size,(n,n))

    def test_07_rounded_alpha_geometry_and_no_coloured_fringe(self):
        for n in SIZES:
            path=OUTPUT/f'portable/png/anamorph-{n}.png';a=image_rgba(path)
            bbox=Image.open(path).getbbox();self.assertIsNotNone(bbox)
            self.assertEqual(bbox[2]-bbox[0],bbox[3]-bbox[1],str(n))
            self.assertTrue(np.all(a[a[:,:,3]==0,:3]==0),str(n))
            self.assertEqual(int(a[0,0,3]),0)
            self.assertEqual(int(a[n//2,n//2,3]),255)
        self.assertEqual(Image.open(OUTPUT/'master/anamorph-rounded-1024.png').getbbox(),(32,32,992,992))

    def test_08_opaque_and_apple_sources(self):
        for name in ('anamorph-opaque-1024','anamorph-square-1024'):
            a=image_rgba(OUTPUT/f'master/{name}.png')
            self.assertEqual(int(a[:,:,3].min()),255)
        im=Image.open(OUTPUT/'apple/Assets.xcassets/AppIcon.appiconset/Anamorph-1024.png')
        self.assertEqual(im.mode,'RGB')
        self.assertEqual(im.size,(1024,1024))
        for path in (OUTPUT/'apple/layers').glob('*.svg'):
            raw=path.read_text()
            self.assertNotRegex(raw,r'<clipPath|<filter|opacity=|mix-blend-mode|<image')
            self.assertIn('<path',raw)
        self.assertIn('NOT a validated .icon', (OUTPUT/'apple/import-manifest.json').read_text())
        self.assertEqual(list(OUTPUT.rglob('*.icon')),[])

    def test_09_ico_internal_sizes_offsets_and_pixels(self):
        path=OUTPUT/'windows/Anamorph.ico';raw=path.read_bytes()
        reserved,kind,count=struct.unpack_from('<HHH',raw)
        self.assertEqual((reserved,kind,count),(0,1,len(ICO_SIZES)))
        dimensions=[]
        ranges=[]
        for i in range(count):
            w,h,_,_,_,bits,length,offset=struct.unpack_from('<BBBBHHII',raw,6+i*16)
            n=w or 256;self.assertEqual(n,h or 256);self.assertEqual(bits,32)
            self.assertGreaterEqual(offset,6+16*count);self.assertLessEqual(offset+length,len(raw))
            ranges.append((offset,offset+length));dimensions.append(n)
            frame=Image.open(io.BytesIO(raw[offset:offset+length])).convert('RGBA')
            self.assertTrue(np.array_equal(np.array(frame),image_rgba(OUTPUT/f'portable/png/anamorph-{n}.png')))
        self.assertEqual(sorted(dimensions),list(ICO_SIZES))
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(sorted(ranges),sorted(ranges)[1:])))
        self.assertEqual(Image.open(path).format,'ICO')

    def test_10_icns_chunks_dimensions_and_pixels(self):
        path=OUTPUT/'macos/Anamorph.icns';raw=path.read_bytes()
        self.assertEqual(raw[:4],b'icns');self.assertEqual(struct.unpack_from('>I',raw,4)[0],len(raw))
        offset=8;sizes=set();types=set();toc=None;headers=[]
        while offset<len(raw):
            kind=raw[offset:offset+4];length=struct.unpack_from('>I',raw,offset+4)[0]
            self.assertGreaterEqual(length,8);self.assertLessEqual(offset+length,len(raw));types.add(kind)
            if kind==b'TOC ':
                toc=raw[offset+8:offset+length]
            else:
                headers.append(raw[offset:offset+8])
                payload=raw[offset+8:offset+length]
                self.assertTrue(payload.startswith(b'\x89PNG\r\n\x1a\n'))
                encoded=Image.open(io.BytesIO(payload));self.assertEqual(encoded.info.get('srgb'),0)
                im=encoded.convert('RGBA');n=im.width;sizes.add(n)
                self.assertEqual(im.size,(n,n))
                self.assertTrue(np.array_equal(np.array(im),image_rgba(OUTPUT/f'portable/png/anamorph-{n}.png')))
            offset+=length
        self.assertEqual(offset,len(raw))
        self.assertEqual(toc,b''.join(headers))
        self.assertEqual(sizes,{16,32,64,128,256,512,1024})
        self.assertTrue({b'icp4',b'icp5',b'icp6',b'ic07',b'ic08',b'ic09',b'ic10',b'ic11',b'ic12',b'ic13',b'ic14'}.issubset(types))
        im=Image.open(path);self.assertEqual(im.format,'ICNS');im.load()

    def test_11_iconset_and_catalog_inventory(self):
        for logical,scale in ICONSET:
            suffix='@2x' if scale==2 else ''
            path=OUTPUT/f'macos/Anamorph.iconset/icon_{logical}x{logical}{suffix}.png'
            self.assertEqual(Image.open(path).size,(logical*scale,)*2)
        for path in OUTPUT.rglob('Contents.json'):
            obj=json.loads(path.read_text())
            for entry in obj.get('images',[]):self.assertTrue((path.parent/entry['filename']).is_file())

    def test_12_small_optical_policy_and_repeatable_raster(self):
        small=P.build_product(self.config,self.historical,small=True)
        normal=P.build_product(self.config,self.historical)
        self.assertEqual(small,(OUTPUT/'master/anamorph-small.svg').read_text())
        self.assertNotIn('<!-- flare_ray_',small)
        self.assertIn('<!-- arc_core -->',small)
        for n in (16,32,64):
            svg=small if n<=32 else normal
            a=R.render_resvg_string(svg,n);b=R.render_resvg_string(svg,n)
            self.assertEqual(a,b)
            arr=np.asarray(Image.open(io.BytesIO(a)).convert('RGBA'))
            target=image_rgba(OUTPUT/f'portable/png/anamorph-{n}.png')
            # Fully transparent RGB values are normalized on export.
            arr=arr.copy();arr[arr[:,:,3]==0,:3]=0
            self.assertTrue(np.array_equal(arr,target),str(n))
            lum=black_rgb(OUTPUT/f'portable/png/anamorph-{n}.png') @ np.array([.2126,.7152,.0722])
            # Readability away from the flare: each curve must light pixels in
            # both the upper and lower body, rather than a lone central spot.
            for y0,y1 in ((n//4,n//2-1),(n//2+1,3*n//4)):
                for x0,x1 in ((n//4,n//2),(n//2,3*n//4)):
                    self.assertGreater(float(lum[y0:y1,x0:x1].max()),25,(n,y0,x0))

    def test_13_highlight_budget(self):
        d=diagnostics(OUTPUT/'master/anamorph-rounded-1024.png')
        self.assertLess(d['all_channels_ge_250_pixels'],1024*1024*.003)

    def test_14_final_review_preserves_published_B0_platform_assets(self):
        # Guard the unchanged-artwork acceptance decision independently of
        # the exporter and its refreshed manifest. Existing checks stay intact.
        control=json.loads((ROOT/'design/final-review.json').read_text())
        for path,expected in control['baseline_platform_sha256'].items():
            current=Path(path)
            if current.parts[0]=='linux':
                current=current.with_name('tech.rolly.anamorph'+current.suffix)
            data=(OUTPUT/current).read_bytes()
            if current.suffix=='.desktop':
                # The signed review remains historical evidence. Undo only the
                # intentional Icon-field rename before comparing its old hash;
                # every other desktop byte, and every image byte, stays guarded.
                data=data.replace(b'Icon=tech.rolly.anamorph\n',
                                  f'Icon={Path(path).stem}\n'.encode())
            self.assertEqual(digest(data),expected,str(current))
        for suffix,key in (('', 'baseline_svg_sha256'),('-small','baseline_small_svg_sha256')):
            self.assertEqual(digest((OUTPUT/f'previews/final/B0{suffix}.svg').read_bytes()),control[key])

    def test_15_linux_desktop_and_hicolor_use_domain_namespace(self):
        base='tech.rolly.anamorph'
        expected={f'linux/{base}.desktop',f'linux/hicolor/scalable/apps/{base}.svg'}
        expected.update(f'linux/hicolor/{n}x{n}/apps/{base}.png' for n in (16,24,32,48,64,128,256,512))
        actual={p.relative_to(OUTPUT).as_posix() for p in (OUTPUT/'linux').rglob('*') if p.is_file()}
        self.assertEqual(actual,expected)
        desktop=(OUTPUT/f'linux/{base}.desktop').read_text()
        self.assertIn(f'\nIcon={base}\n',desktop)
        self.assertIn('\nExec=Anamorph\n',desktop)
        for n in (16,24,32,48,64,128,256,512):
            self.assertEqual((OUTPUT/f'linux/hicolor/{n}x{n}/apps/{base}.png').read_bytes(),
                             (OUTPUT/f'portable/png/anamorph-{n}.png').read_bytes())
        self.assertEqual((OUTPUT/f'linux/hicolor/scalable/apps/{base}.svg').read_bytes(),
                         (OUTPUT/'master/anamorph.svg').read_bytes())


def cross_renderer(engine='auto'):
    inkscape=shutil.which('inkscape')
    if engine=='inkscape' or (engine=='auto' and inkscape):
        if not inkscape:raise RuntimeError('Inkscape explicitly requested but unavailable')
        version=subprocess.check_output([inkscape,'--version'],text=True).strip()
        result={'status':'executed','engine':'inkscape','version':version,'sizes':{}}
        with tempfile.TemporaryDirectory(prefix='anamorph-inkscape-') as td:
            for n in (32,128,512,1024):
                svg=OUTPUT/('master/anamorph-small.svg' if n<=32 else 'master/anamorph.svg')
                path=Path(td)/f'{n}.png'
                subprocess.run([inkscape,str(svg),f'--export-width={n}',f'--export-height={n}',
                                f'--export-filename={path}'],check=True,capture_output=True,timeout=60)
                difference=np.abs(black_rgb(path)-black_rgb(OUTPUT/f'portable/png/anamorph-{n}.png'))
                stats={'mae':round(float(difference.mean()),5),
                       'p99_channel_error':round(float(np.percentile(difference,99)),3),
                       'max_channel_error':round(float(difference.max()),3)}
                result['sizes'][str(n)]=stats
                if stats['mae']>3:raise RuntimeError(f'Inkscape/resvg review threshold exceeded at {n}: {stats}')
        return result
    chrome,how,state=R.chromium_status()
    if state=='absent':
        if engine=='chromium':raise RuntimeError('Chromium explicitly requested but unavailable: '+how)
        return {'status':'skipped: optional renderer absent','discovery':how}
    if state=='misconfigured':raise RuntimeError('Configured Chromium is unusable: '+how)
    result={'status':'executed','engine':'chromium','discovery':how,'sizes':{}}
    for n in (32,128,512,1024):
        svg=OUTPUT/('master/anamorph-small.svg' if n<=32 else 'master/anamorph.svg')
        # Historical render.py intentionally stays byte-identical. Its launcher
        # assumes a headless-shell binary; a desktop Chromium needs --headless.
        # Use a real viewport and crop unused space, never resize small artwork.
        with tempfile.TemporaryDirectory(prefix='anamorph-chromium-') as td:
            td=Path(td);html=td/'icon.html';shot=td/'icon.png'
            html.write_text('<!doctype html><meta charset="utf-8">'
                            '<style>html,body{margin:0;background:black}'
                            f'svg{{display:block;width:{n}px;height:{n}px}}</style>'+svg.read_text())
            command=[chrome,'--headless','--no-sandbox','--disable-gpu',
                     '--disable-dev-shm-usage','--hide-scrollbars','--disable-background-networking',
                     '--no-first-run','--force-device-scale-factor=1',
                     f'--user-data-dir={td/"profile"}',f'--screenshot={shot}',
                     f'--window-size={max(500,n)},{max(500,n)}',html.as_uri()]
            proc=subprocess.run(command,capture_output=True,timeout=60)
            if proc.returncode:raise RuntimeError('Chromium execution failed: '+proc.stderr.decode(errors='replace')[-1500:])
            png=shot.read_bytes()
        chrome_im=Image.open(io.BytesIO(png)).convert('RGB')
        if chrome_im.width<n or chrome_im.height<n:raise RuntimeError('Chromium screenshot smaller than requested')
        other=np.asarray(chrome_im.crop((0,0,n,n))).astype(float)
        ours=black_rgb(OUTPUT/f'portable/png/anamorph-{n}.png')
        difference=np.abs(ours-other)
        stats={'mae':round(float(difference.mean()),5),'p99_channel_error':round(float(np.percentile(difference,99)),3),
               'max_channel_error':round(float(difference.max()),3)}
        result['sizes'][str(n)]=stats
        if stats['mae']>3.0:raise RuntimeError(f'Cross-renderer MAE exceeds documented 3/255 review threshold at {n}: {stats}')
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cross-renderer',action='store_true')
    ap.add_argument('--engine',choices=['auto','inkscape','chromium'],default='auto',
                    help='Independent renderer: auto prefers Inkscape when installed; explicit engines must work')
    ap.add_argument('--report',type=Path)
    args=ap.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProductTests))
    report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'source_revision':ProductTests.manifest['source_revision'],
            'geometry':geometry_diagnostics(),
            'selected':diagnostics(OUTPUT/'master/anamorph-rounded-1024.png'),
            'historical':diagnostics(ROOT/'out/render_1024.png'),
            'cross_renderer':cross_renderer(args.engine) if args.cross_renderer else {'status':'not requested'},
            'native_platforms':'not executed: macOS/Windows toolchains and desktop OS sessions unavailable'}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    if not result.wasSuccessful():raise SystemExit(1)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
