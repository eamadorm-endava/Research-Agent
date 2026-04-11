#!/usr/bin/env python3
import re
import sys

INVALID = r'[\\/:*?"<>|]'


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean(text: str) -> str:
    text = text.replace("/", "-").replace("\\", "-")
    text = re.sub(INVALID, "", text)
    return normalize_space(text)


def build_filename(meeting_date: str, meeting_name: str) -> str:
    date_part = clean(meeting_date) if meeting_date else "undated"
    name_part = clean(meeting_name) if meeting_name else "Unnamed Meeting"
    return f"{date_part} - {name_part} - Meeting Summary.docx"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: build_filename.py <meeting-date> <meeting-name>")
        sys.exit(1)
    print(build_filename(sys.argv[1], sys.argv[2]))
