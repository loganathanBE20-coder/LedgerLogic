import xml.etree.ElementTree as ET
import math
import re
import os
from collections import Counter


def fetch_constituency_names():
    """Parse constituency.txt to build {number: name} mapping."""
    mapping = {}
    try:
        with open('constituency.txt', 'r', encoding='utf-8') as f:
            for line in f:
                match = re.search(r'(?:^|\t)(\d+)\s+([^\t\n]+)', line)
                if match:
                    no = int(match.group(1))
                    name = match.group(2).strip()
                    mapping[no] = name
        print(f"Loaded {len(mapping)} names from constituency.txt")
    except Exception as e:
        print("Error reading constituency.txt:", e)
    for i in range(1, 235):
        if i not in mapping:
            mapping[i] = f"Constituency {i}"
    return mapping

def get_polygon_centroid(poly):
    pts_str = poly.attrib.get('points', '')
    if not pts_str:
        return None, None, []
    pts = pts_str.strip().split()
    coords = []
    for p in pts:
        if ',' in p:
            cx, cy = p.split(',')
            coords.append((float(cx), float(cy)))
    if not coords:
        return None, None, []
    cx = sum(c[0] for c in coords) / len(coords)
    cy = sum(c[1] for c in coords) / len(coords)
    return cx, cy, coords


def polygon_area(coords):
    n = len(coords)
    if n < 3: return 0
    area = 0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]
    return abs(area) / 2

def preprocess_svg(input_file, output_file):
    names_map = fetch_constituency_names()
    
    ET.register_namespace('', "http://www.w3.org/2000/svg")
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    tree = ET.parse(input_file)
    root = tree.getroot()
    parent_map = {c: p for p in tree.iter() for c in p}
    
    def is_inset(x, y):
        if x > 900 and y < 450: return True
        if x < 350 and y < 350: return True
        if x > 750 and y > 800: return True
        if x > 900: return True
        return False
    
    # STEP 1: Extract main-map labels only
    text_group = root.find(".//svg:g[@id='Textelemente']", ns)
    main_labels = []
    if text_group is not None:
        for text_el in list(text_group):
            if text_el.tag.endswith('text'):
                txt = text_el.text.strip() if text_el.text else ""
                transform = text_el.attrib.get('transform', '')
                x, y = 0, 0
                m = re.search(r'matrix\([^\)]+\s+([-\d\.]+)\s+([-\d\.]+)\)', transform)
                if m:
                    x, y = float(m.group(1)), float(m.group(2))
                if txt.isdigit() and not is_inset(x, y):
                    num = int(txt)
                    if 1 <= num <= 234:
                        main_labels.append({'no': num, 'x': x, 'y': y})
    
    # Deduplicate labels - keep only one per constituency number
    seen_nos = {}
    unique_labels = []
    for lbl in main_labels:
        if lbl['no'] not in seen_nos:
            seen_nos[lbl['no']] = True
            unique_labels.append(lbl)
    main_labels = unique_labels
    print(f"Unique main-map labels: {len(main_labels)}")
    
    # STEP 2: Remove ALL text, rect, line, path elements
    if text_group is not None:
        for el in list(text_group):
            text_group.remove(el)
    for g in root.findall('.//svg:g', ns):
        for el in list(g.findall('svg:text', ns)):
            g.remove(el)
    for tag_name in ['{http://www.w3.org/2000/svg}text', 'text']:
        for el in list(root.iter(tag_name)):
            if el in parent_map:
                parent_map[el].remove(el)
    for tag in ['rect', 'line', 'path']:
        for el in root.findall(f".//svg:{tag}", ns):
            if el in parent_map:
                parent_map[el].remove(el)
    
    # STEP 3: Collect valid main-map polygons (remove insets)
    polygons = root.findall(".//svg:polygon", ns)
    valid_polygons = []
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    
    for poly in polygons:
        cx, cy, coords = get_polygon_centroid(poly)
        if cx is None: continue
        if is_inset(cx, cy):
            if poly in parent_map:
                parent_map[poly].remove(poly)
            continue
        for px, py in coords:
            min_x, min_y = min(min_x, px), min(min_y, py)
            max_x, max_y = max(max_x, px), max(max_y, py)
        valid_polygons.append({
            'el': poly, 'cx': cx, 'cy': cy,
            'coords': coords, 'area': polygon_area(coords)
        })
    
    print(f"Main-map polygons: {len(valid_polygons)}")
    
    # STEP 4: For each label, find the SINGLE closest polygon 
    # (label-centric matching ensures each label maps to exactly one polygon)
    label_to_poly = {}  # label_idx -> polygon_idx
    poly_taken = set()
    
    # Sort labels by how "isolated" they are (fewer nearby polygons = match first)
    # This prevents dense urban labels from stealing rural polygons
    label_scores = []
    for li, lbl in enumerate(main_labels):
        dists = sorted([math.hypot(p['cx'] - lbl['x'], p['cy'] - lbl['y']) 
                        for p in valid_polygons])
        # Score = distance to closest polygon (smaller = easier to match)
        label_scores.append((dists[0] if dists else 999, li))
    label_scores.sort()
    
    for _, li in label_scores:
        lbl = main_labels[li]
        best_pi = None
        best_dist = float('inf')
        for pi, poly in enumerate(valid_polygons):
            if pi in poly_taken:
                continue
            dist = math.hypot(poly['cx'] - lbl['x'], poly['cy'] - lbl['y'])
            if dist < best_dist:
                best_dist = dist
                best_pi = pi
        if best_pi is not None:
            label_to_poly[li] = best_pi
            poly_taken.add(best_pi)
    
    print(f"Matched: {len(label_to_poly)} labels to polygons")
    
    # Verify uniqueness
    poly_ids = list(label_to_poly.values())
    assert len(poly_ids) == len(set(poly_ids)), "Polygon IDs not unique!"
    label_nos = [main_labels[li]['no'] for li in label_to_poly]
    no_counts = Counter(label_nos)
    dupes = {k: v for k, v in no_counts.items() if v > 1}
    assert not dupes, f"Duplicate constituency numbers: {dupes}"
    print("All IDs unique - no duplicates")
    
    # STEP 5: Inject data attributes
    matched_ids = set()
    for li, pi in label_to_poly.items():
        poly_el = valid_polygons[pi]['el']
        no = main_labels[li]['no']
        name = names_map.get(no, f"Constituency {no}")
        poly_el.attrib['data-id'] = str(no)
        poly_el.attrib['data-name'] = name
        poly_el.attrib['id'] = f"constituency-{no}"
        if 'class' in poly_el.attrib:
            del poly_el.attrib['class']
        matched_ids.add(no)
    
    # Clean class attr from unmatched polygons
    for pi, pd in enumerate(valid_polygons):
        if pi not in poly_taken and 'class' in pd['el'].attrib:
            del pd['el'].attrib['class']
    
    missing = sorted(set(range(1, 235)) - matched_ids)
    print(f"Matched {len(matched_ids)}/234 | Missing: {len(missing)} -> {missing}")
    
    # STEP 6: Write output
    padding = 20
    vb = f"{min_x-padding} {min_y-padding} {max_x-min_x+padding*2} {max_y-min_y+padding*2}"
    root.attrib['viewBox'] = vb
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    print(f"Wrote {output_file} | ViewBox: {vb}")


if __name__ == "__main__":
    preprocess_svg(
        'Wahlkreise_zur_Vidhan_Sabha_von_Tamil_Nadu.svg',
        'static/tn_map_processed.svg'
    )
