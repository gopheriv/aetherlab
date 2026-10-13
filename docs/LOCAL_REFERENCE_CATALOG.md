# Local physics references and ENT source mocks

PhysLab reads the local folder `~/Projects/References` by default. You can point
the app at another folder with `AETHERLAB_REFERENCE_SOURCES`. The source files
are left in place; ZIP archives are listed without unpacking them, and the app
extracts only the one file the user opens.

## UNT-focused school textbooks used as references

| Grade | Kept textbooks |
| --- | --- |
| 7 | Кронгарт |
| 8 | Закирова |
| 9 | Закирова |
| 10 | Закирова (ЖМ) |
| 11 | Закирова (ЖМ) |

This keeps one continuous Kazakhstan school-physics track for grades 8–11 and
the only grade-7 textbook in the folder. Duplicate editions from the other
series remain untouched on disk, but are hidden from this curated app catalog
and excluded from its reference index. Formula/theory references are grouped
with the books. The ENT specification is shown as an exam reference, not as a
question set. Text-searchable PDFs are included in the textbook RAG index
during Re-index or lesson preparation. Scanned textbooks remain openable, but
are not indexed as text until OCR is available.

## Question sources shown as mock sets

- `Testcenter -3.pdf`, `Testcenter -4.pdf`, `Testcenter -5.pdf`
- `ФИЗИКА ҰТО ҮЛГІ КІТАП 2021.pdf.pdf`
- Physics-only items under `ЕНТ Физика` in `7. ЕНТ-1.zip` and `7. ЕНТ-2.zip`,
  including named variants, answer sets, and `Testcenter -6.pdf`

The archives contain other school subjects and non-test physics resources.
Only the physics folder is included in this catalog; quarterly school
assessments (СОР/СОЧ/БЖБ/ТЖБ), other subjects, and images are excluded from the
ENT mock list. Physics files whose names do not identify them as a test or
variant are kept in a separate “type not specified” group for manual review.

The PDF/Word/PowerPoint source sets open in the computer's associated viewer.
They are not automatically converted into scored PhysLab questions. Built-in
practice uses a separate 100-item authored bank; its keyed records are
mirrored in SQLite, and the fixed 40-item, 50-point mock remains separate.
