"""OCR embedded images on image-only slides in physics PPTX references."""

from __future__ import annotations

import io
import posixpath
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from index_reference_library import _database_path, _ocr_image

from aetherlab.core.console import configure_utf8_stdio

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DRAW_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PRES_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SLIDE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")


def main() -> int:
    configure_utf8_stdio()
    from PIL import Image

    db_path = _database_path()
    db = sqlite3.connect(db_path, timeout=60)
    candidates = db.execute(
        """SELECT source_id,source_path,archive_member,filename FROM source_files
           WHERE extension='.pptx' AND (filename LIKE '%физик%' COLLATE NOCASE
             OR filename LIKE '%physics%' COLLATE NOCASE
             OR archive_member LIKE '%физик%' COLLATE NOCASE
             OR archive_member LIKE '%physics%' COLLATE NOCASE)
           ORDER BY filename COLLATE NOCASE"""
    ).fetchall()
    updated = 0
    for source_id, source_path, member, filename in candidates:
        if not member:
            continue
        print(f"OCR embedded slide images: {filename}", flush=True)
        with ZipFile(source_path) as outer, outer.open(member) as pptx_file:
            payload = pptx_file.read()
        with ZipFile(io.BytesIO(payload)) as pptx:
            slide_names = sorted((n for n in pptx.namelist() if SLIDE.match(n)),
                                 key=lambda n: int(SLIDE.match(n).group(1)))
            for slide_name in slide_names:
                slide_number = int(SLIDE.match(slide_name).group(1))
                existing = db.execute(
                    "SELECT unit_id,text,status FROM content_units WHERE source_id=? AND unit_number=? AND unit_type='slide'",
                    (source_id, slide_number),
                ).fetchone()
                if not existing:
                    continue
                slide_xml = ET.fromstring(pptx.read(slide_name))
                image_ids = [
                    node.attrib.get(f"{{{R_NS}}}embed")
                    for picture in slide_xml.iter(f"{{{PRES_NS}}}pic")
                    for node in picture.iter(f"{{{DRAW_NS}}}blip")
                ]
                if not image_ids:
                    continue
                rels_name = f"ppt/slides/_rels/slide{slide_number}.xml.rels"
                if rels_name not in pptx.namelist():
                    continue
                rels = ET.fromstring(pptx.read(rels_name))
                targets = {
                    item.attrib.get("Id"): posixpath.normpath(posixpath.join("ppt/slides", item.attrib.get("Target", "")))
                    for item in rels.findall(f"{{{REL_NS}}}Relationship")
                    if item.attrib.get("Type", "").endswith("/image")
                }
                texts: list[str] = []
                confidences: list[float] = []
                for rel_id in dict.fromkeys(image_ids):
                    target = targets.get(rel_id)
                    if not target or target not in pptx.namelist():
                        continue
                    try:
                        text, confidence, _ = _ocr_image(Image.open(io.BytesIO(pptx.read(target))))
                    except Exception as exc:  # preserve OCR status per slide
                        print(f"  slide {slide_number}: {type(exc).__name__}: {exc}", flush=True)
                        continue
                    if text.strip():
                        texts.append(text.strip())
                    if confidence is not None:
                        confidences.append(confidence)
                combined = "\n".join(texts)
                # Avoid replacing usable speaker notes or slide text.
                if not combined:
                    continue
                previous_text = existing[1].strip()
                final_text = previous_text if previous_text else combined
                confidence = (sum(confidences) / len(confidences)) if confidences else None
                status = "indexed" if confidence is None or confidence >= 0.55 else "ocr_low_confidence"
                db.execute(
                    "UPDATE content_units SET text=?,extraction_method=?,confidence=?,status=? WHERE unit_id=?",
                    (final_text, "pptx_embedded_image_tesseract_kaz_rus_eng", confidence, status, existing[0]),
                )
                db.execute("DELETE FROM reference_fts WHERE rowid=?", (existing[0],))
                db.execute(
                    "INSERT INTO reference_fts(rowid,source_id,unit_number,unit_type,title,label,text) VALUES(?,?,?,?,?,?,?)",
                    (existing[0], source_id, slide_number, "slide", filename, f"Slide {slide_number}", final_text),
                )
                updated += 1
                if updated % 10 == 0:
                    db.commit()
                    print(f"  OCR slides updated: {updated}", flush=True)
    db.commit()
    db.execute(
        """UPDATE source_files SET
           text_units=(SELECT COUNT(*) FROM content_units u WHERE u.source_id=source_files.source_id AND u.extraction_method='pptx_xml_text_and_notes' AND trim(u.text)<>''),
           ocr_units=(SELECT COUNT(*) FROM content_units u WHERE u.source_id=source_files.source_id AND u.extraction_method LIKE 'pptx_embedded_image_tesseract%'),
           empty_units=(SELECT COUNT(*) FROM content_units u WHERE u.source_id=source_files.source_id AND trim(u.text)='')
           WHERE extension='.pptx'"""
    )
    db.commit()
    print(f"OCR complete: {updated} physics PPTX slides updated")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
