#!/usr/bin/env python3
"""Constrained B experiments and four final review sheets; no canonical writes.

Called by the product exporter, sharing its direct renderer and PNG encoder.
The pinned B0 configuration/hash preserves a clean control and small fallback.
Experiments adjust derived in-memory states, never historical parameters.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'design/final-review.json'
BACKGROUNDS = (('Near-black', '#080c12', '#d2deeb'),
               ('Medium dark', '#252d38', '#d2deeb'),
               ('Neutral gray', '#808080', '#ffffff'),
               ('Light', '#edf0f4', '#162534'))


def replace_once(svg, old, new):
    if svg.count(old) != 1:
        raise ValueError('Review experiment anchor changed: ' + old[:70])
    return svg.replace(old, new, 1)


def experiment(P, spec, historical, name, small=False):
    config = copy.deepcopy(spec['baseline_config'])
    h = copy.deepcopy(historical)
    if name == 'S1':
        config['small']['core_width_gain'] = 1.50
    elif name == 'S2':
        config['small'].update(flare_gain=.65, glow_gain=.70)
    for layer in h['layers']:
        if name == 'F1' and layer['id'] == 'flare_core_w':
            layer['r'] *= .94
            layer['color'] = [c * 1.12 for c in layer['color']]
        if name == 'F2' and layer['id'] in ('flare_halo', 'flare_core_w'):
            gain = .88 if layer['id'] == 'flare_halo' else 1.06
            layer['color'] = [c * gain for c in layer['color']]
    svg = P.build_product(config, h, 'B', small=small)
    if name == 'B1':
        start = svg.index('<linearGradient id="product-edge"')
        end = svg.index('</linearGradient>', start) + len('</linearGradient>')
        old_edge = svg[start:end]
        edge = old_edge
        for old, new in [('stop-opacity="0.55"', 'stop-opacity="0.60"'),
                         ('stop-opacity="0.2"', 'stop-opacity="0.26"'),
                         ('stop-opacity="0.32"', 'stop-opacity="0.40"')]:
            edge = replace_once(edge, old, new)
        svg = replace_once(svg, old_edge, edge)
        svg = replace_once(svg, 'stroke="url(#product-edge)" stroke-width="1.6"',
                           'stroke="url(#product-edge)" stroke-width="2.0"')
    elif name == 'B2':
        gradient = ('<radialGradient id="review-depth" cx="0.24" cy="0.08" r="0.8">'
                    '<stop stop-color="#27465e" stop-opacity="0.16"/>'
                    '<stop offset="1" stop-color="#27465e" stop-opacity="0"/>'
                    '</radialGradient>')
        svg = replace_once(svg, '</defs>', gradient + '</defs>')
        field = f'<path d="{P.body_path(config)}" fill="url(#product-field)"/>'
        svg = replace_once(svg, field, field +
                           f'<path d="{P.body_path(config)}" fill="url(#review-depth)"/>')
    elif name not in ('B0', 'F1', 'F2', 'S1', 'S2'):
        raise ValueError(name)
    if name == 'B0':
        expected = spec['baseline_small_svg_sha256' if small else 'baseline_svg_sha256']
        if hashlib.sha256(svg.encode()).hexdigest() != expected:
            raise ValueError('B0 no longer reproduces the pinned published SVG')
    return svg


def make_review(package, P, config, historical, selected, small, apple, png_bytes):
    spec = json.loads(SPEC.read_text())
    vectors = {name: (experiment(P, spec, historical, name),
                      experiment(P, spec, historical, name, True))
               for name in spec['variants']}
    # Exact experiment vectors make even rejected alternatives independently
    # inspectable; regular and small differ only by the documented size policy.
    for name, pair in vectors.items():
        for index, svg in enumerate(pair):
            if name in ('S1', 'S2') and index == 0:
                continue  # Their regular master is exactly B0, not a new design.
            suffix = '-small' if index else ''
            package.put(f'previews/final/{name}{suffix}.svg', svg,
                        'Final review experiment; not a selected platform asset',
                        dimensions=[1024, 1024], variant=name, transparency=True)

    def font(n=14):
        return ImageFont.load_default(size=n)

    def put(sheet, path, purpose):
        package.put('previews/final/' + path, png_bytes(sheet), purpose,
                    variant='final review', transparency=False)

    def icon(sheet, svg, n, x, y):
        im = package.image(svg, n)
        sheet.paste(im, (x, y), im)

    def actual(name, n):
        return vectors[name][int(n <= config['small']['maximum_size'])]

    # Three equal actual 256 px canvases. B-final may intentionally equal B0.
    sheet = Image.new('RGB', (900, 360), '#252d38'); d = ImageDraw.Draw(sheet)
    for i, (label, svg) in enumerate([
            ('Historical reconstruction', (ROOT / 'reconstruction.svg').read_text()),
            ('Published B0 / control', vectors['B0'][0]),
            ('B-final / selected B0', selected)]):
        d.text((i*300+20, 18), label, font=font(17), fill='#e8eff8')
        d.text((i*300+20, 44), '256 px / actual pixels', font=font(12), fill='#b6c6d7')
        icon(sheet, svg, 256, i*300+20, 80)
    put(sheet, 'before-after.png', 'Historical / B0 / selected final, equal native 256 px')

    # One compact candidate sheet: edge at 256/64/32, flare at 128/64/32,
    # small policy at 16/20/24/32 with regular 40/48 for the transition.
    sheet = Image.new('RGB', (1140, 1568), '#252d38'); d = ImageDraw.Draw(sheet)
    sections = [('Boundary / B0 vs B1 vs B2', ('B0','B1','B2'), (256,64,32), 420),
                ('Central source / F0 = B0', ('B0','F1','F2'), (128,64,32), 228),
                ('Small policy / regular at 40 and 48', ('B0','S1','S2'), (16,20,24,32,40,48), 136)]
    y = 0
    for heading, names, sizes, height in sections:
        for _, bg, fg in (BACKGROUNDS[0], BACKGROUNDS[-1]):
            d.rectangle((0,y,1139,y+height-1), fill=bg)
            d.text((16,y+10), heading + ' / ' + bg, font=font(16), fill=fg)
            for col, name in enumerate(names):
                x = col*380+18
                d.text((x,y+38), name, font=font(16), fill=fg)
                if sizes[0] == 256:
                    icon(sheet, actual(name,256),256,x,y+64)
                    for n, dx in ((64,0),(32,112)):
                        d.text((x+dx,y+330),str(n),font=font(12),fill=fg)
                        icon(sheet,actual(name,n),n,x+dx,y+350)
                else:
                    dx = 0
                    for n in sizes:
                        d.text((x+dx,y+60),str(n),font=font(12),fill=fg)
                        icon(sheet,actual(name,n),n,x+dx,y+82)
                        dx += max(n+24,55)
            y += height
    put(sheet, 'candidates.png', 'Constrained B boundary, flare and small factors, native pixels on light/dark')

    sizes = (256,128,64,48,40,32,24,20,16)
    sheet = Image.new('RGB', (1080, 1560)); d = ImageDraw.Draw(sheet)
    for row, (name,bg,fg) in enumerate(BACKGROUNDS):
        y = row*390;d.rectangle((0,y,1079,y+389),fill=bg)
        d.text((16,y+12),f'B-final / {name} {bg} / native pixels',font=font(16),fill=fg)
        x = 16
        for n in sizes:
            d.text((x,y+42),str(n)+' px',font=font(12),fill=fg)
            icon(sheet,small if n<=32 else selected,n,x,y+64)
            x += max(n+24,64)
        # Generic launcher row supplies surrounding UI without pretending to be
        # a screenshot from GNOME, Finder, Windows or a tested native session.
        d.text((16,y+338),'Simulated launcher:',font=font(12),fill=fg)
        for col, color in enumerate(('#526475','#765e71','#405e65','#706b54')):
            x=180+col*68
            if col != 2:
                d.rounded_rectangle((x,y+330,x+47,y+377),radius=11,fill=color)
        icon(sheet,selected,48,316,y+330)
        icon(sheet,small,32,480,y+338)
    put(sheet, 'backgrounds.png', 'Final native 16..256 exports on four backgrounds and labelled simulated launcher')

    parts = [P.build_apple_layer(config,historical,n).split('</defs>\n',1)[1].rsplit('</svg>',1)[0]
             for n in ('left','right','interaction')]
    colors = config['candidates'][config['selected']]['background']
    field = ('<linearGradient id="native-field" x2="0.75" y2="1">'
             f'<stop stop-color="{colors[0]}"/><stop offset="1" stop-color="{colors[1]}"/>'
             '</linearGradient>')
    content = '<rect width="1024" height="1024" fill="url(#native-field)"/>'+''.join(parts)
    flat = P.svg_document(field, content, 'Unmasked native layer source / no native material')
    mask = '<clipPath id="preview-mask"><path d="'+P.body_path(config,True)+'"/></clipPath>'
    approximate = P.svg_document(field+mask,'<g clip-path="url(#preview-mask)">'+content+'</g>',
                                 'Approximate mask preview / NOT Apple rendering')
    sheet=Image.new('RGB',(1168,400),'#edf0f4');d=ImageDraw.Draw(sheet)
    labels=[('Independent body','32 unit inset / authored glow',selected),
            ('Flat square fallback','Full bleed / no enclosure edge',apple),
            ('Native source composition','Unmasked / no system effects',flat),
            ('Approximate mask preview','Full bleed / NO native rendering',approximate)]
    for i,(name,note,svg) in enumerate(labels):
        x=i*292+18;d.text((x,16),name,font=font(15),fill='#162534')
        d.text((x,42),note,font=font(12),fill='#162534');icon(sheet,svg,256,x,78)
    d.text((18,356),'Only the standalone body is pre-rounded. Do not feed it into the Apple system-mask route.',
           font=font(15),fill='#162534')
    put(sheet,'masking.png','Independent / full-bleed flat / unmasked native layers / approximate mask, no Apple effects')
